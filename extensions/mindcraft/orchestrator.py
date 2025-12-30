"""
Mindcraft Village Builder Orchestrator

Guides Andy the master builder through construction projects.
Provides unlimited supplies via RCON - no resource gathering needed!
Uses Claude LLM for intelligent project management.
"""

import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from .client import MindcraftClient
from .monitor import MindcraftMonitor
from .planner import MindcraftPlanner
from .detector import detect_mindcraft_config
from .persistence import MindcraftPersistence

PROMPTS_DIR = Path(__file__).parent / "prompts"


class MindcraftOrchestrator:
    """
    Multi-Mode Orchestration Engine.

    Modes:
    - builder: Village building, construction projects
    - helper: Follow and assist players
    - defender: Combat, protection, mob hunting

    Provides supplies via RCON and uses Claude LLM for intelligent guidance.
    """

    MODES = {
        "builder": {
            "prompt_file": "mode_builder.md",
            "description": "Village building, construction projects",
            "kit": "builder",
        },
        "helper": {
            "prompt_file": "mode_helper.md",
            "description": "Follow and assist players",
            "kit": "helper",
        },
        "defender": {
            "prompt_file": "mode_defender.md",
            "description": "Combat, protection, mob hunting",
            "kit": "defender",
        },
    }

    def __init__(self, dry_run: bool = False, server_url: Optional[str] = None, mode: str = "builder"):
        # Load config
        self.config = detect_mindcraft_config() or {}

        # Overrides
        if dry_run:
            self.config["dry_run"] = True
        if server_url:
            self.config["server_url"] = server_url

        self.dry_run = self.config.get("dry_run", False)
        server = self.config.get("server_url", "ws://localhost:8080")

        # Set mode
        self.mode = mode.lower() if mode.lower() in self.MODES else "builder"
        mode_info = self.MODES[self.mode]

        mode_icons = {"builder": "🏗️", "helper": "🤝", "defender": "⚔️"}
        icon = mode_icons.get(self.mode, "🤖")

        print(f"{icon}  Initializing Orchestrator")
        print(f"   Server: {server}")
        print(f"   Mode: {self.mode.upper()} - {mode_info['description']}")

        # Components
        self.client = MindcraftClient(server_url=server, dry_run=self.dry_run)
        self.persistence = MindcraftPersistence()
        self.monitor = MindcraftMonitor(
            client=self.client, persistence=self.persistence
        )
        self.planner = MindcraftPlanner(monitor=self.monitor, dry_run=self.dry_run)

        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

        # LLM response settings
        self.RESPONSE_INTERVAL = 30  # Check every 30 seconds
        self._last_response_time: dict = {}
        self._last_known_message: dict = {}
        self._pending_llm_call = False

        # Building zone - Andy can build in a larger area
        self.HOME_BASE = {"x": 288, "y": 80, "z": -48}
        self.MAX_DISTANCE_FROM_HOME = 500  # Larger area for village building
        self._last_home_check: dict = {}
        self.HOME_CHECK_INTERVAL = 120  # Check less frequently

        # RCON settings
        self.MINECRAFT_CONTAINER = "minecraft-minecraft-1"
        self._last_kit_given: dict = {}
        self.KIT_COOLDOWN = 300  # 5 minutes between builder kits

        # Stuck detection
        self._last_positions: dict = {}  # agent -> (x, y, z, timestamp)
        self._stuck_count: dict = {}  # agent -> count of stationary checks
        self.STUCK_THRESHOLD = 3  # After 3 stationary checks, consider stuck
        self.MIN_SURFACE_Y = 75  # Below this Y level, agent might be underground

        # Mode-specific kits
        self.KITS = {
            "builder": [
                # Tools
                ("diamond_pickaxe", 1),
                ("diamond_axe", 1),
                ("diamond_shovel", 1),
                # Food
                ("cooked_beef", 64),
                # Basic building blocks
                ("oak_planks", 256),
                ("cobblestone", 256),
                ("stone_bricks", 256),
                ("glass", 128),
                # Decorative
                ("torch", 128),
                ("lantern", 64),
                ("oak_door", 16),
                ("glass_pane", 128),
                # Roofing
                ("oak_stairs", 128),
                ("cobblestone_stairs", 128),
                # Special
                ("crafting_table", 4),
                ("chest", 8),
            ],
            "helper": [
                # Tools
                ("diamond_pickaxe", 1),
                ("diamond_axe", 1),
                ("diamond_shovel", 1),
                # Food
                ("cooked_beef", 64),
                # Helpful items
                ("torch", 128),
                ("cobblestone", 64),
                ("oak_planks", 64),
                # Light armor
                ("iron_helmet", 1),
                ("iron_chestplate", 1),
                ("iron_leggings", 1),
                ("iron_boots", 1),
                ("shield", 1),
            ],
            "defender": [
                # Weapons
                ("netherite_sword", 1),
                ("bow", 1),
                ("arrow", 128),
                ("shield", 1),
                # Full armor
                ("netherite_helmet", 1),
                ("netherite_chestplate", 1),
                ("netherite_leggings", 1),
                ("netherite_boots", 1),
                # Food
                ("cooked_beef", 64),
                ("golden_apple", 8),
                # Utility
                ("torch", 64),
                ("diamond_pickaxe", 1),
            ],
        }

        # Current kit based on mode
        self.CURRENT_KIT = self.KITS.get(self.mode, self.KITS["builder"])

        # Common material aliases for request parsing
        self.MATERIAL_ALIASES = {
            "wood": "oak_planks",
            "planks": "oak_planks",
            "stone": "cobblestone",
            "brick": "bricks",
            "glass": "glass",
            "door": "oak_door",
            "torch": "torch",
            "stairs": "oak_stairs",
            "slab": "oak_slab",
            "fence": "oak_fence",
            "wool": "white_wool",
            "concrete": "white_concrete",
            "terracotta": "terracotta",
            "sandstone": "sandstone",
            "quartz": "quartz_block",
            "iron": "iron_block",
            "gold": "gold_block",
            "diamond": "diamond_block",
        }

        # Load mode-specific system prompt
        prompt_file = PROMPTS_DIR / mode_info["prompt_file"]
        try:
            with open(prompt_file, "r") as f:
                self.system_prompt = f.read()
            print(f"   Prompt: {mode_info['prompt_file']}")
        except FileNotFoundError:
            print(f"   ⚠️ Prompt file not found: {prompt_file}")
            self.system_prompt = f"You are an orchestrator for Andy in {self.mode} mode."

    async def start(self):
        """Start the village builder system."""
        if self._running:
            return

        print("🏗️  Starting Village Builder System...")

        # 1. Connect Client
        print("   Connecting to MindServer...")
        if not await self.client.connect():
            print("❌ Failed to connect. Exiting.")
            return

        # 2. Start Monitor
        print("   Starting Monitor...")
        await self.monitor.start()

        # 3. Start Loop
        self._running = True
        self._loop_task = asyncio.create_task(self._main_loop())

        print("✅ Village Builder Online!")
        print("   Andy will receive building projects and unlimited supplies.")

        # Keep running until stopped
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self):
        """Gracefully stop the system."""
        print("\n🛑 Stopping Village Builder...")
        self._running = False

        if self._loop_task:
            self._loop_task.cancel()

        await self.monitor.stop()
        await self.client.disconnect()
        print("✅ System Stopped.")

    async def _main_loop(self):
        """The heartbeat of the builder system."""
        print("💓 Builder loop active")

        while self._running:
            try:
                # 1. Update Planner
                self.planner.update()

                # 2. Check for stuck agents FIRST - rescue before anything else
                await self._check_and_rescue_stuck_agents()

                # 3. Check if agents need supplies (builder kit or requested materials)
                await self._check_and_provide_supplies()

                # 4. Check agents and respond with LLM (building guidance)
                await self._check_and_respond_to_agents()

                # 5. Check building zone boundaries
                await self._check_building_zone()

                # 6. Sleep tick
                await asyncio.sleep(1.0)

            except Exception as e:
                print(f"⚠️ Error in main loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(1.0)

    # ==================== Stuck Detection & Rescue ====================

    async def _check_and_rescue_stuck_agents(self):
        """Detect stuck agents and teleport them to safety."""
        import math
        now = time.time()
        agents = self.client.get_all_agents()

        if not agents:
            return

        for agent_name, agent_state in agents.items():
            if agent_state.status.value != "online":
                continue

            pos = agent_state.position
            if not pos:
                continue

            current_pos = (pos[0], pos[1], pos[2])

            # Skip invalid positions (Y=0 is usually a default/null value)
            if current_pos[1] == 0 or current_pos[1] is None:
                continue

            # Check rescue cooldown (don't spam rescues)
            last_rescue = self._last_positions.get(f"{agent_name}_rescue", 0)
            if isinstance(last_rescue, (int, float)) and (now - last_rescue) < 60:
                continue  # Don't rescue more than once per minute

            # Check if agent is underground (but not at Y=0 which is invalid)
            if 0 < current_pos[1] < self.MIN_SURFACE_Y:
                print(f"⚠️ {agent_name} is underground at Y={current_pos[1]:.0f}! Teleporting to surface...")
                await self._rescue_agent(agent_name, "underground")
                self._last_positions[f"{agent_name}_rescue"] = now
                continue

            # Check if position has changed since last check
            last_data = self._last_positions.get(agent_name)

            if last_data and isinstance(last_data, tuple) and len(last_data) == 2:
                last_pos, last_time = last_data
                if isinstance(last_pos, tuple) and len(last_pos) == 3:
                    dx = abs(current_pos[0] - last_pos[0])
                    dy = abs(current_pos[1] - last_pos[1])
                    dz = abs(current_pos[2] - last_pos[2])
                    distance_moved = math.sqrt(dx*dx + dy*dy + dz*dz)

                    # If barely moved in 30+ seconds (increased from 10)
                    if distance_moved < 2 and (now - last_time) > 30:
                        self._stuck_count[agent_name] = self._stuck_count.get(agent_name, 0) + 1

                        if self._stuck_count[agent_name] >= self.STUCK_THRESHOLD:
                            print(f"⚠️ {agent_name} appears stuck at ({current_pos[0]:.0f}, {current_pos[1]:.0f}, {current_pos[2]:.0f})!")
                            await self._rescue_agent(agent_name, "stationary")
                            self._stuck_count[agent_name] = 0
                            self._last_positions[f"{agent_name}_rescue"] = now
                    else:
                        # Agent is moving, reset stuck count
                        self._stuck_count[agent_name] = 0

            # Update last known position
            self._last_positions[agent_name] = (current_pos, now)

    async def _rescue_agent(self, agent_name: str, reason: str):
        """Teleport a stuck agent to a safe location."""
        print(f"🚁 Rescuing {agent_name} ({reason})...")

        # Teleport to a safe spot above spawn
        home_x = self.HOME_BASE["x"]
        home_y = self.HOME_BASE["y"] + 5  # A bit above ground
        home_z = self.HOME_BASE["z"]

        await self._run_rcon(f"tp {agent_name} {home_x} {home_y} {home_z}")
        print(f"   📍 Teleported to ({home_x}, {home_y}, {home_z})")

        # Clear any negative effects and heal
        await self._run_rcon(f"effect clear {agent_name}")
        await self._run_rcon(f"effect give {agent_name} minecraft:instant_health 1 5")
        await self._run_rcon(f"effect give {agent_name} minecraft:saturation 999999 255 true")
        await self._run_rcon(f"effect give {agent_name} minecraft:resistance 999999 4 true")

        # Notify the agent
        await self.client.send_message(
            agent_name,
            f"You were stuck ({reason})! I've teleported you back to the village center. "
            f"You're safe now - ready to continue building?"
        )

    # ==================== RCON Supply Methods ====================

    async def _run_rcon(self, command: str) -> Optional[str]:
        """Execute an RCON command on the Minecraft server."""
        if self.dry_run:
            print(f"   [DRY RUN] RCON: {command}")
            return "dry_run"

        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "exec", self.MINECRAFT_CONTAINER,
                "rcon-cli", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=10.0
            )

            if result.returncode != 0:
                print(f"⚠️ RCON error: {stderr.decode()[:100]}")
                return None

            return stdout.decode().strip()

        except asyncio.TimeoutError:
            print("⚠️ RCON timeout")
            return None
        except Exception as e:
            print(f"⚠️ RCON exception: {e}")
            return None

    async def _give_item(self, player: str, item: str, count: int = 1) -> bool:
        """Give an item to a player via RCON."""
        # Ensure item has minecraft: prefix handling
        if not item.startswith("minecraft:"):
            item_name = f"minecraft:{item}"
        else:
            item_name = item

        command = f"give {player} {item_name} {count}"
        result = await self._run_rcon(command)
        return result is not None

    async def _give_builder_kit(self, agent_name: str) -> bool:
        """Give a full builder kit to an agent."""
        print(f"🏗️  Giving builder kit to {agent_name}...")

        success_count = 0
        for item, count in self.CURRENT_KIT:
            if await self._give_item(agent_name, item, count):
                success_count += 1
                print(f"   ✓ {item} x{count}")
            else:
                print(f"   ✗ Failed: {item} x{count}")

        # Set to creative-like conditions
        await self._run_rcon(f"effect give {agent_name} minecraft:saturation 999999 255 true")
        await self._run_rcon(f"effect give {agent_name} minecraft:resistance 999999 4 true")
        print(f"   ✨ Applied builder buffs (saturation, resistance)")

        return success_count >= len(self.CURRENT_KIT) // 2  # At least half succeeded

    async def _give_requested_supplies(self, agent_name: str, items: List[Tuple[str, int]]) -> bool:
        """Give specific requested supplies to an agent."""
        print(f"📦 Fulfilling supply request for {agent_name}...")

        success_count = 0
        for item, count in items:
            # Resolve aliases
            resolved_item = self.MATERIAL_ALIASES.get(item.lower(), item)
            if await self._give_item(agent_name, resolved_item, count):
                success_count += 1
                print(f"   ✓ {resolved_item} x{count}")
            else:
                print(f"   ✗ Failed: {resolved_item} x{count}")

        return success_count > 0

    def _parse_supply_request(self, message: str) -> List[Tuple[str, int]]:
        """Parse a message for supply requests."""
        if not message:
            return []

        message_lower = message.lower()

        # Keywords that indicate a supply request
        request_keywords = ["need", "give", "want", "get", "more", "supply", "supplies", "out of", "running low"]

        if not any(kw in message_lower for kw in request_keywords):
            return []

        items = []

        # Pattern: "need/want/give me X <material>" or "<number> <material>"
        # Match patterns like "64 cobblestone", "more wood", "need glass"
        patterns = [
            r'(\d+)\s+([\w_]+)',  # "64 cobblestone"
            r'(?:need|want|give|get|more)\s+(?:me\s+)?(?:some\s+)?(\d*)\s*([\w_]+)',  # "need more wood"
        ]

        for pattern in patterns:
            matches = re.findall(pattern, message_lower)
            for match in matches:
                if len(match) == 2:
                    count_str, material = match
                    count = int(count_str) if count_str and count_str.isdigit() else 64
                    # Skip common non-material words
                    if material not in ["to", "the", "a", "an", "some", "help", "it", "that", "this"]:
                        items.append((material, min(count, 256)))  # Cap at 256

        # Also check for material names mentioned without numbers
        for alias, actual in self.MATERIAL_ALIASES.items():
            if alias in message_lower and not any(alias in item[0] for item in items):
                items.append((actual, 64))

        return items

    async def _check_and_provide_supplies(self):
        """Check if agents need supplies and provide them."""
        now = time.time()
        agents = self.client.get_all_agents()

        if not agents:
            return

        for agent_name, agent_state in agents.items():
            if agent_state.status.value != "online":
                continue

            # Skip if agent is stuck (let rescue handle it)
            if self._stuck_count.get(agent_name, 0) >= self.STUCK_THRESHOLD - 1:
                continue

            # Check cooldown - strict enforcement
            last_kit = self._last_kit_given.get(agent_name, 0)
            if (now - last_kit) < self.KIT_COOLDOWN:
                continue

            # Check if they asked for supplies in their last message
            last_msg = agent_state.last_message or ""
            requested_items = self._parse_supply_request(last_msg)

            # Give requested supplies (with cooldown check already done above)
            if requested_items:
                print(f"\n📦 {agent_name} requested supplies!")
                await self._give_requested_supplies(agent_name, requested_items)
                self._last_kit_given[agent_name] = now
                await self.client.send_message(
                    agent_name,
                    "Supplies incoming! Check your inventory and keep building!"
                )
                continue

            # Check inventory for low supplies
            inv = agent_state.inventory or []
            inv_count = sum(item.get("count", 0) for item in inv)

            # Only give builder kit if inventory is VERY low (not just low)
            # and only on death/respawn or truly empty
            if inv_count < 20:
                needs_kit = False
                reason = ""

                # Check for death/respawn
                if "died" in last_msg.lower() or "respawn" in last_msg.lower():
                    needs_kit = True
                    reason = "respawned"
                elif inv_count == 0:
                    needs_kit = True
                    reason = "empty inventory"

                if needs_kit:
                    print(f"\n🆘 {agent_name} needs builder kit: {reason}")
                    success = await self._give_builder_kit(agent_name)
                    self._last_kit_given[agent_name] = now

                    if success:
                        await self.client.send_message(
                            agent_name,
                            "Builder kit delivered! You have tools, blocks, and decorations. "
                            "Time to build something amazing! What will you create?"
                        )

    # ==================== LLM Response Methods ====================

    async def _check_and_respond_to_agents(self):
        """Check agent states and respond with building guidance."""
        if self._pending_llm_call:
            return

        now = time.time()
        agents = self.client.get_all_agents()

        if not agents:
            return

        for agent_name, agent_state in agents.items():
            if agent_state.status.value != "online":
                continue

            # Initialize tracking for new agents
            if agent_name not in self._last_response_time:
                self._last_response_time[agent_name] = now
                self._last_known_message[agent_name] = ""
                await self._send_llm_response(agent_name, agent_state, is_initial=True)
                continue

            # Check timing
            time_since_response = now - self._last_response_time[agent_name]
            if time_since_response < self.RESPONSE_INTERVAL:
                continue

            # Check for new message or idle state
            current_message = agent_state.last_message or ""
            last_known = self._last_known_message.get(agent_name, "")

            should_respond = (
                current_message != last_known or
                agent_state.current_action == "Idle" or
                time_since_response > 120
            )

            if should_respond:
                self._last_known_message[agent_name] = current_message
                await self._send_llm_response(agent_name, agent_state)
                self._last_response_time[agent_name] = now

    async def _send_llm_response(self, agent_name: str, agent_state, is_initial: bool = False):
        """Generate and send building guidance via LLM."""
        self._pending_llm_call = True

        try:
            context = self._build_agent_context(agent_name, agent_state, is_initial)
            response = await self._call_llm(context)

            if response:
                # Check if LLM response mentions giving supplies
                if "supplies" in response.lower() or "giving" in response.lower() or "send" in response.lower():
                    # Give some relevant supplies based on the project
                    await self._give_requested_supplies(agent_name, [
                        ("cobblestone", 128),
                        ("oak_planks", 128),
                        ("glass", 64),
                        ("torch", 64),
                    ])

                print(f"\n🧠 Building guidance for {agent_name}:")
                print(f"   {response[:100]}{'...' if len(response) > 100 else ''}")
                await self.client.send_message(agent_name, response)
            else:
                print(f"⚠️ LLM returned empty response for {agent_name}")

        except Exception as e:
            print(f"⚠️ LLM Error for {agent_name}: {e}")
        finally:
            self._pending_llm_call = False

    def _build_agent_context(self, agent_name: str, agent_state, is_initial: bool = False) -> str:
        """Build context for building-focused guidance."""
        pos = agent_state.position or (0, 0, 0)
        pos_str = f"X={pos[0]:.0f}, Y={pos[1]:.0f}, Z={pos[2]:.0f}"

        # Inventory summary
        inv_summary = "Empty"
        if agent_state.inventory:
            items = []
            for item in agent_state.inventory[:15]:
                name = item.get("name", "unknown").replace("minecraft:", "")
                count = item.get("count", 1)
                items.append(f"{name}x{count}")
            inv_summary = ", ".join(items) if items else "Empty"

        context = f"""AGENT: {agent_name} (Master Builder)
POSITION: {pos_str}
CURRENT ACTION: {agent_state.current_action or "Idle"}
INVENTORY: {inv_summary}
LAST MESSAGE: {agent_state.last_message or "(none)"}
VILLAGE CENTER: X=288, Y=80, Z=-48
"""

        if is_initial:
            context += "\nSITUATION: Builder just connected. Assign their first building project near the village center!"
        elif "done" in (agent_state.last_message or "").lower() or "complete" in (agent_state.last_message or "").lower() or "finished" in (agent_state.last_message or "").lower():
            context += "\nSITUATION: Builder completed a project! Praise their work and assign the next building in the master plan."
        elif "need" in (agent_state.last_message or "").lower() or "supplies" in (agent_state.last_message or "").lower():
            context += "\nSITUATION: Builder is requesting supplies. Confirm you're sending them and encourage continued building."
        elif agent_state.current_action == "Idle":
            context += "\nSITUATION: Builder is idle. Assign a new construction project!"
        elif "stuck" in (agent_state.last_message or "").lower() or "help" in (agent_state.last_message or "").lower():
            context += "\nSITUATION: Builder needs help. Provide building tips or suggest a different approach."
        else:
            context += "\nSITUATION: Check on building progress and provide encouragement or next steps."

        return context

    async def _call_llm(self, context: str) -> Optional[str]:
        """Call Claude CLI for building guidance."""
        if self.dry_run:
            return "Build a nice wooden house near spawn! Use !newAction to start construction."

        if not shutil.which("claude"):
            print("⚠️ Claude CLI not found, using fallback")
            return self._fallback_response(context)

        try:
            full_prompt = f"""{self.system_prompt}

---
CURRENT STATE:
{context}

---
Respond with a SHORT (1-2 sentences max) building instruction or project assignment.
Focus on CONSTRUCTION - never tell them to gather resources.
If they need materials, say "Supplies incoming!" and I will give them items.
Include a specific building task or !newAction command when appropriate."""

            process = await asyncio.create_subprocess_exec(
                "claude",
                "-p", full_prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0
            )

            if process.returncode != 0:
                print(f"⚠️ Claude CLI error: {stderr.decode()[:200]}")
                return self._fallback_response(context)

            response = stdout.decode().strip()

            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            return response if response else self._fallback_response(context)

        except asyncio.TimeoutError:
            print("⚠️ Claude CLI timeout")
            return self._fallback_response(context)
        except Exception as e:
            print(f"⚠️ Claude CLI exception: {e}")
            return self._fallback_response(context)

    def _fallback_response(self, context: str) -> str:
        """Fallback building instructions when LLM unavailable."""
        if "just connected" in context.lower() or "first" in context.lower():
            return "Welcome, builder! Start with a 7x7 wooden house near spawn. Use !newAction('Build a 7x7 oak plank house with door and windows at coordinates 300, 80, -50')"
        elif "complete" in context.lower() or "done" in context.lower():
            return "Great work! Next project: Build a cobblestone watchtower nearby, at least 15 blocks tall with a torch beacon at the top."
        elif "idle" in context.lower():
            return "Time to build! Create a stone path connecting your buildings. Use !newAction('Build a 3-wide cobblestone path from spawn to the nearest house')"
        else:
            return "Keep building! Remember to add windows and interior details to make buildings feel alive."

    async def _check_building_zone(self):
        """Gently remind builders to stay in the village area."""
        import math

        now = time.time()
        monitor_status = self.monitor.get_monitor_status()
        agent_states = monitor_status.get("agent_states", {})

        for agent_name, state in agent_states.items():
            if agent_name not in self._last_home_check:
                self._last_home_check[agent_name] = now
                continue

            time_since_check = now - self._last_home_check[agent_name]
            if time_since_check < self.HOME_CHECK_INTERVAL:
                continue

            self._last_home_check[agent_name] = now

            position = state.get("position", {})
            if not position:
                continue

            agent_x = position.get("x", 0)
            agent_z = position.get("z", 0)

            dx = agent_x - self.HOME_BASE["x"]
            dz = agent_z - self.HOME_BASE["z"]
            distance = math.sqrt(dx * dx + dz * dz)

            if distance > self.MAX_DISTANCE_FROM_HOME:
                print(f"🏗️  {agent_name} is {int(distance)} blocks from village center")
                await self.client.send_message(
                    agent_name,
                    f"You're getting far from the village! The master plan focuses on the area around X=288, Z=-48. "
                    f"Head back to continue the community build!"
                )


async def run_orchestrator(dry_run: bool = False, server_url: Optional[str] = None, mode: str = "builder"):
    """Entry point helper."""
    orchestrator = MindcraftOrchestrator(dry_run=dry_run, server_url=server_url, mode=mode)

    loop = asyncio.get_running_loop()

    def handle_signal():
        print("\nReceived stop signal")
        asyncio.create_task(orchestrator.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await orchestrator.start()


def print_usage():
    """Print usage information."""
    print("Usage: python -m extensions.mindcraft.orchestrator [OPTIONS]")
    print("")
    print("Options:")
    print("  --mode MODE    Set orchestrator mode (builder, helper, defender)")
    print("  --dry-run      Run without making actual changes")
    print("")
    print("Modes:")
    print("  builder   - Village building, construction projects (default)")
    print("  helper    - Follow and assist players")
    print("  defender  - Combat, protection, mob hunting")
    print("")
    print("Examples:")
    print("  python -m extensions.mindcraft.orchestrator --mode helper")
    print("  python -m extensions.mindcraft.orchestrator --mode defender")


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        sys.exit(0)

    dry_run_arg = "--dry-run" in sys.argv

    # Parse mode
    mode = "builder"
    for i, arg in enumerate(sys.argv):
        if arg == "--mode" and i + 1 < len(sys.argv):
            mode = sys.argv[i + 1]

    asyncio.run(run_orchestrator(dry_run=dry_run_arg, mode=mode))
