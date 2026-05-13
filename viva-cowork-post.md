**Teaching Copilot Cowork where the stores are**

A lot of folks on the team have been asking me how I get so much mileage out of AI day to day. The honest answer is that the model isn't doing anything magic. I've just spent some time teaching it where things live. With Microsoft 365 Copilot Cowork now rolling out through Frontier, that same trick is sitting right inside our own tenant, waiting for us to use it.

If you're earlier in your AI journey, stick with me. This is going to be simple.

**Quick context on Cowork**

Cowork is the new "do the work" mode in Microsoft 365 Copilot. Instead of just chatting, it carries out multi-step tasks across Outlook, Teams, SharePoint, OneDrive, your calendar, and Office documents. You describe an outcome, it makes a plan, you approve the sensitive actions, and it goes. Under the hood, Microsoft partnered with Anthropic so Cowork is reasoning with Claude inside our M365 tenant, grounded in our content through Work IQ and respecting our existing permissions. (So yes, the same family of models I've been raving about, now talking directly to our SharePoint.)

**The mall directory analogy**

Picture your work life as a shopping mall. When Cowork starts a fresh conversation, it knows the mall exists but it doesn't know what you actually care about. Anchor stores could be on either end. The little kiosk with the report you need is tucked behind the escalator. You can either walk Cowork past every storefront every single time (slow, expensive, frustrating), or you can hand it the big "You Are Here" directory by the entrance.

Cowork has two kinds of directories:

- **Built-in skills** are the anchor stores Cowork already knows about. Word, Excel, PowerPoint, PDF, Email, Scheduling, Calendar Management, Meetings, Daily Briefing, Enterprise Search, Communications, Deep Research, Adaptive Cards. You don't set these up. They light up automatically when the conversation calls for them.
- **Custom skills** are the storefronts you add to the directory yourself. This is the part that quietly changes how you work.

**How custom skills actually work**

Custom skills live in your OneDrive at `Documents/Cowork/skills/`. Each skill is its own subfolder containing a file called `SKILL.md`. Cowork scans that folder at the start of every conversation and decides which skills to load based on what you're asking. You don't tell it to "use the weekly report skill," it picks the right one on its own.

A skill file is just plain text with a tiny header. Here's what one looks like:

```
---
name: Q3 Ops Review
description: Reference and analyze the Q3 operations review report.
---

The full Q3 operations review report lives in the Ops Leadership
SharePoint site under "Quarterly Reviews / Q3-Review.docx".
Do not load this file preemptively. Only open it when the
conversation actually touches Q3 operations topics.
```

That's the whole thing. Cowork reads the `description` line to decide if the skill is relevant. If it is, it loads the rest and follows the instructions.

You can have up to 50 custom skills. Each one can carry up to 20 companion files (templates, reference docs, scripts), so your "Q3 Ops Review" skill could include the actual report, the slide template you always use to present it, and the email template you send afterward. All sitting quietly in OneDrive until the conversation needs them.

**Why this is the unlock for our team**

We live in SharePoint and OneDrive. Cowork already has read access to everything we have permission to see, through Microsoft Graph. That's the part that makes this magic. You're not uploading files, not copy-pasting reports into a chat box, not re-explaining who the stakeholders are. The skill is just a pointer that says "if the topic is X, here's the shelf, here's the playbook, here's who cares about it."

I can casually say "what did we decide about the regional split in Q3?" and Cowork already knows where to walk. No briefing required.

The "do not load preemptively" line in that example matters. You want the directory entry, not the entire store inventory. Loading a 90 page report into every conversation is slow and wasteful. Walking into that store only when the topic comes up is exactly what a good shopper does.

**Where the idea came from for me**

I'd been doing the same thing in a side project of mine called Context Foundry, a little pattern-learning system I tinker with on weekends. Every plugin in it has a `SKILL.md` file pointing to playbooks and reference material. When Microsoft announced Cowork in March, I read the docs and laughed, because the file format is almost identical. Same `SKILL.md` name, same YAML frontmatter, same idea. The pattern won. It's now sitting in your OneDrive, ready to use.

**Where to start, if this is new to you**

You don't need a perfect setup on day one. Pick one recurring task you'd love to stop re-explaining. Then:

1. In OneDrive, create the folder `Documents/Cowork/skills/<your-skill-name>/`.
2. Add a `SKILL.md` file with a one-line description and three or four sentences of instructions, including pointers to the SharePoint sites or files that matter.
3. Try it. Open Cowork and ask a question that should trigger it. Watch the side panel to see if your skill loads.

Then let Cowork help you grow it. Every time you catch yourself re-explaining something for the third time, just say "update my skill to remember that." Within a couple of weeks your conversations get shorter and the output gets noticeably sharper. The mall directory fills in.

**A few questions I've been getting**

**Isn't this just a fancy prompt? Why do I need a file?**
A prompt lives for one conversation. A SKILL.md lives forever and loads automatically whenever the topic comes up. The whole point is that you stop typing the same context every Monday morning.

**Do I need Cowork to do this today?**
Cowork is rolling out through the Frontier preview program right now, so not everyone in the org has it yet. If you do, you'll see it in your Microsoft 365 Copilot home alongside Chat and Search. If you don't, this is still worth reading so you're ready the day it lands in your tenant. The directory analogy and the SKILL.md format aren't going anywhere.

**Is this safe? What about permissions?**
Cowork only sees what you'd see. It uses Microsoft Graph under your account, so the same SharePoint, OneDrive, Teams, and Outlook permissions you have today apply. If a teammate doesn't have access to a SharePoint site, Cowork won't pull anything from it for them either. Skills are stored in your personal OneDrive, so they aren't shared unless you share that folder.

**Do I need to be technical to write a SKILL.md?**
No. It's a text file with five or six lines of English at the top. If you can write an email explaining where something lives and when it matters, you can write a skill. You can even ask Cowork itself to write the skill for you. Just tell it what you want to remember and where the files are.

**What if I make a mistake and put bad instructions in a skill?**
You'll notice quickly because Cowork's responses will feel off. Open the file in OneDrive, edit it, save it. Next conversation picks up the new version. There's no deploy step, no review board, no IT ticket.

Happy to sit down with anyone who wants to try this. Drop a comment or send me a chat. We're early in the Frontier rollout, so there's room to experiment and shape how the team uses it.
