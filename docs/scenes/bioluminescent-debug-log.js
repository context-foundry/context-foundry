// Scene: Bioluminescent Debug Log
// Toyama Bay, Toyama, Japan
window.CF.register("Bioluminescent Debug Log", "Toyama Bay, Toyama, Japan", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Firefly squid glow particles
  var squids=[], numSquids=30;
  for(var i=0;i<numSquids;i++){
    squids.push({
      x:Math.random()*W,
      y:H-25-Math.random()*30,
      vy:(Math.random()*0.5)-0.2,
      flicker:Math.random()*0.5+0.5,
      life:Math.random()*20+10
    });
  }

  // Fishing boats
  var boats=[], numBoats=5;
  for(var i=0;i<numBoats;i++){
    boats.push({
      x:(Math.random() * W),
      y:H-30-Math.random()*20,
      sway:Math.random() * Math.PI * 2,
      glow:Math.random() * 5
    });
  }

  // Shore lights
  var shoreLights=[], numLights=15;
  for(var i=0;i<numLights;i++){
    shoreLights.push({
      x:(Math.random() * W),
      y:H-10-Math.random()*10,
      intensity:Math.random()*0.4+0.1
    });
  }

  return function(t){
    // Dark ocean surface
    rect(0, 0, W, H-40, '#0b0c2a');

    // Ocean waves
    for(var x=0; x<W; x+=2){
      var waveY = Math.sin((x + t * 5) * 0.02) * 2;
      px(x, H-40 + waveY, '#1a1a5e');
    }

    // Draw firefly squid glow
    for(var squid of squids){
      squid.y += squid.vy;
      if(squid.y > H-30) {
        squid.y = H-25-Math.random()*30;
        squid.x = Math.random() * W;
      }
      var glow = Math.abs(Math.sin(t * 3 + squid.x * 0.1)) * squid.flicker;
      if(glow > 0.3) {
        circle(squid.x, squid.y, 2, rgba('#00e5ff', glow));
      }
    }

    // Draw fishing boats
    for(var boat of boats){
      boat.swag += 0.02;
      var boatX = boat.x + Math.sin(boat.swag) * 3;
      rect(boatX, boat.y, 15, 5, '#1a1a5e');
      var boatGlow = Math.abs(Math.sin(t * 4 + boat.x)) * boat.glow;
      if(boatGlow > 0.1) {
        circle(boatX + 7, boat.y - 3, 3, rgba('#00ff87', boatGlow));
      }
    }

    // Draw shore lights
    for(var light of shoreLights){
      rect(light.x, light.y, 5, 1, rgba('#48cae4', light.intensity));
    }

    // Bottom glow line for brand consistency
    rect(0,H-1,W,1,rgba('#00e5ff',0.4));
    rect(0,H-2,W,1,rgba('#00e5ff',0.1));
  };
});