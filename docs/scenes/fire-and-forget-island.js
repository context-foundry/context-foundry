// Scene: Fire and Forget Island
// Surtsey, Vestmannaeyjar, Iceland
window.CF.register("Fire and Forget Island", "Surtsey, Vestmannaeyjar, Iceland", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Lava flow particles
  var lavaParticles=[];
  for(var i=0;i<40;i++){
    lavaParticles.push({x:Math.random()*W,y:H-30+Math.random()*30,vx:(Math.random()-0.5)*2,life:50+Math.random()*50,maxLife:100});
  }

  // Steam columns
  var steamColumns=[];
  function createSteamColumn(x){
    for(var i=0;i<20;i++){
      steamColumns.push({x:x,y:H-30+i*Math.random()*20+Math.cos(i)*5,life:30+Math.random()*20});
    }
  }
  for(var i=60;i<420;i+=60) createSteamColumn(i);

  return function(t){
    // Background gradient (sky)
    for(var y=0;y<80;y++){
      var p=y/80;
      var color=lerp('#495057','#1d1d1d',p);
      rect(0,y,W,1,color);
    }

    // Sea
    for(var y=80;y<H;y++){
      var p=(y-80)/(H-80);
      var color=lerp('#48cae4','#90e0ef',p);
      rect(0,y,W,1,color);
    }

    // Lava flow animation
    for(var p of lavaParticles){
      p.y -= 0.5; // Move up
      if(p.life>0){
        px(p.x,p.y,rgba('#e85d04',p.life/p.maxLife));
        p.life--;
      }
      if(p.life <= 0){
        p.x = Math.random() * W;
        p.y = H - 30 + Math.random() * 30;
        p.life = 50 + Math.random() * 50;
      }
    }

    // Draw new volcanic island
    var islandY = H - 30;
    var islandWidth = 100;
    rect((W/2)-islandWidth/2,islandY,islandWidth,30,'#1d1d1d');
    for(var x=(W/2)-islandWidth/2;x<(W/2)+islandWidth/2;x+=8){
      px(x,islandY-Math.random()*10,'#495057');
    }

    // Lava meeting the sea
    for(var x=(W/2)-islandWidth/2;x<(W/2)+islandWidth/2;x++){
      if (Math.random() < 0.05) {
        rect(x,islandY,1,1,rgba('#e85d04',0.8));
      }
    }

    // Steam columns animation
    for(var s of steamColumns){
      s.y -= 0.2; // Rise upwards
      if(s.life > 0){
        px(s.x,s.y,rgba('#ffffff',s.life/50));
        s.life--;
      }
      // Reset column if it dies
      if(s.life <= 0){
        s.x = Math.random() * W;
        s.y = H - 30 + Math.random() * 20;
        s.life = 30 + Math.random() * 20;
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#e85d04',0.3));
    rect(0,H-2,W,1,rgba('#e85d04',0.1));
  };
});