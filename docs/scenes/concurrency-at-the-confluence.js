// Scene: Concurrency at the Confluence
// Meeting of Waters, Manaus, Brazil
window.CF.register("Concurrency at the Confluence", "Meeting of Waters, Manaus, Brazil", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Particle systems for bubbles
  var bubbles=[];
  for(var i=0;i<50;i++){
    bubbles.push({x:Math.random()*W,y:H-Math.random()*50,vy:-1-(Math.random()*2),vx:(Math.random()-0.5)*1,life:10+Math.random()*20,maxLife:30});
  }

  // River dolphins array
  var dolphins=[];
  var dolphinCount=2;
  for(var i=0;i<dolphinCount;i++){
    dolphins.push({
      x:Math.random()*W*0.5+W*0.25, // Ensure dolphins are in the Amazon section
      y:H-40-Math.random()*20,
      phase:Math.random()*Math.PI*2,
      size:5+Math.random()*5,
      speed:0.2 + Math.random()*0.2
    });
  }

  return function(t){
    // Sky gradient
    for(var y=0;y<H*0.4;y++){
      var p=y/(H*0.4);
      rect(0,y,W,1,lerp('#0077b6','#264653',p));
    }

    // Water surface
    for(var y=H*0.4;y<H*0.7;y++){
      var p=(y-H*0.4)/(H*0.3);
      var color=lerp('#2d6a4f','#6b705c',p);
      rect(0,y,W,1,color);
    }

    // Dark Rio Negro and Sandy Amazon Water Interface
    for(var x=0;x<W;x++){
      px(x,H*0.7+Math.sin(x*0.1-t*0.5)*2,rgba('#1c242a',0.6)); // Rio Negro
      px(x,H*0.7,rgba('#dda15e',0.5)); // Sandy Amazon Water
    }

    // Draw dolphins
    for(var d of dolphins){
      d.x += Math.cos(d.phase) * d.speed; // Moving in a smooth sinusoidal path
      d.phase += 0.05; // Increment phase for animation
      if(d.x > W) d.x = -20; // Reset dolphin position 

      // Draw Dolphin shape
      for(var dy=-d.size;dy<=d.size;dy++){
        for(var dx=-d.size;dx<=d.size;dx++){
          if(dx*dx + dy*dy <= d.size*d.size){
            px(d.x+dx, d.y+dy, '#ffffff'); // White dolphin body
          }
        }
      }
    }

    // Bubbles animation
    for(var b of bubbles){
      b.y += b.vy;
      b.x += b.vx + Math.sin(t*2+b.x*0.05)*0.2; // Bubbles drifting a bit sideways
      b.life--;
      if(b.life<=0 || b.y<50){
        b.x=Math.random()*W;
        b.y=H-Math.random()*50; // reset bubble position
        b.life=10+Math.random()*20; // reset life
      }
      var a=(b.life/b.maxLife)*0.3;
      circle(b.x,b.y,2,rgba('#ffffff',a)); // Draw bubbles
      px(b.x-1,b.y-1,rgba('#ffffff',a*0.6)); // Highlights
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#dda15e',0.3));
    rect(0,H-2,W,1,rgba('#6b705c',0.15));
  };
});