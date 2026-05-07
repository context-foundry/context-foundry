// Scene: Spawn Point: Galapagos
// Galapagos Islands, Ecuador
window.CF.register("Spawn Point: Galapagos", "Galapagos Islands, Ecuador", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Particle systems for atmosphere
  var bubbles=[];
  for(var i=0;i<40;i++){
    bubbles.push({x:0,y:0,vx:(Math.random()-0.5)*0.2,vy:-Math.random()*0.5-0.2,life:0,maxLife:0});
  }
  
  // Function to emit bubbles
  function emitBubble(sx,sy){
    for(var b of bubbles){
      if(b.life<=0){
        b.x=sx;
        b.y=sy;
        b.vx=(Math.random()-0.5)*0.2;
        b.vy=-Math.random()*0.5-0.2;
        b.maxLife=30+Math.random()*30;
        b.life=b.maxLife;
        break;
      }
    }
  }

  // Initialize random number generators
  var sr=srand(42);

  return function(t){
    // Background gradient: ocean to volcanic rocks
    for(var y=0;y<H;y++){
      var p=y/H;
      var col=lerp('#2a9d8f','#1d1d1d',p);
      rect(0,y,W,1,col);
    }

    // Volcanic rocks
    rect(0,H-40,W,40,'#1d1d1d');
    for(var i=0;i<20;i++){
      var x1=Math.floor(sr()*W);
      var x2=Math.floor(sr()*W);
      rect(x1,H-40+(Math.random()*10),x2,H-30,'#264653');
      if(Math.random()<0.3)px(x1+x2/2,H-40+(Math.random()*10),rgba('#e9c46a',0.5));
    }

    // Marine Iguana Animation
    var iguanaX=(t*20)%W;
    var iguanaY=H-40+Math.sin(t)*3;
    rect(iguanaX,H-44,10,4,'#264653');
    rect(iguanaX+2,H-45,6,1,'#1d1d1d');
    px(iguanaX,H-42,'#2a9d8f');

    // Blue-footed Booby
    var boobyX=(W*0.75+Math.sin(t)*30)%W;
    var boobyY=H-60+Math.sin(t*0.5)*2;
    rect(boobyX,boobyY,6,1,'#ffffff'); // body
    px(boobyX+1,boobyY-1,'#e9c46a'); // head
    rect(boobyX+2,boobyY-1,1,1,'#48cae4'); // foot

    // Giant Tortoise Animation
    var tortoiseX=(W*0.2+Math.cos(t*0.3)*10)%W;
    var tortoiseY=H-30;
    circle(tortoiseX,tortoiseY,12,'#264653');
    circle(tortoiseX,tortoiseY,10,'#2a9d8f');

    // Emitting bubbles from tortoise
    emitBubble(tortoiseX,tortoiseY);

    // Draw bubbles
    for(var b of bubbles){
      if(b.life>0){
        b.x+=b.vx;
        b.y+=b.vy;
        b.life--;
        var a=(b.life/b.maxLife);
        circle(b.x,b.y,2,rgba('#48cae4',a));
      }
    }

    // Bottom glow line for water surface
    rect(0,H-1,W,1,rgba('#48cae4',0.4));
    rect(0,H-2,W,1,rgba('#48cae4',0.1));
  };
});