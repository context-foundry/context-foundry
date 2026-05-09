// Scene: Promise.allSettled() Sunset
// Okavango Delta, Botswana
window.CF.register("Promise.allSettled() Sunset", "Okavango Delta, Botswana", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Waterway particles
  var waterEffects=[];
  for(var i=0;i<40;i++){
    waterEffects.push({x:Math.random()*480,y:Math.random()*60,alpha:Math.random()*0.3+0.1});
  }

  // Elephant herd
  var elephants=[];
  for(var i=0;i<5;i++){
    elephants.push({
      x:Math.random()*400,y:H-60-Math.random()*40,
      sway:Math.random()*2*Math.PI,
      speed:0.5+Math.random()*1,
      size:8+Math.floor(Math.random()*4)
    });
  }

  // Initialize random number generator
  var sr=srand(77);

  return function(t){
    // Gradient sky
    for(var y=0;y<H/2;y++){
      var p=y/(H/2);
      rect(0,y,W,1,lerp('#264653','#e9c46a',p));
    }
    for(var y=H/2;y<H;y++){
      var p=(y-H/2)/(H/2);
      rect(0,y,W,1,lerp('#e9c46a','#f4a261',p));
    }

    // Waterways
    for(var y=150;y<220;y+=4){
      for(var x=0;x<W;x++){
        var wave=Math.sin((x+y)*0.05+t*0.2)*0.5;
        var col=lerp('#f4a261','#2d6a4f',(y-150)/70+wave*0.1);
        px(x,y,col);
      }
    }

    // Water effect particles
    for(var p of waterEffects){
      p.x += (Math.random() - 0.5) * 0.5;
      p.y += Math.sin(t + p.x * 0.1) * 0.2;
      if (p.y > 260) {
        p.y = 0;
        p.x = Math.random() * 480;
      }
      px(p.x, p.y, rgba('#ffffff', p.alpha));
    }

    // Draw elephants
    for(var e of elephants){
      e.x += e.speed;
      if(e.x > W) e.x = -30;
      var baseY = H - 60;
      
      // Body
      rect(e.x, baseY, e.size+2, e.size, '#e76f51');
      
      // Trunk
      rect(e.x + 2, baseY - e.size/2, 2, e.size/2, '#cc4c3b');
      
      // Ears
      px(e.x, baseY + e.size/2 - 1, '#e76f51');
      px(e.x + e.size + 1, baseY + e.size/2 - 1, '#e76f51');

      // Swaying motion
      e.sway += e.speed * 0.05 * Math.sin(e.x * 0.1 + t);
      var swayAngle = Math.sin(e.sway) * 3;

      // Feet
      rect(e.x + swayAngle, baseY + e.size, 4, 4, '#2d6a4f');
      rect(e.x + swayAngle + e.size, baseY + e.size, 4, 4, '#2d6a4f');
    }

    // Papyrus reeds in foreground
    for(var i=0;i<30;i++){
      var reedX = Math.random() * 480;
      var reedY = H - Math.random() * 50 - 10;
      for(var j=0;j<Math.random()*8+2;j++){
        px(reedX, reedY-j, '#2d6a4f');
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#f4a261',0.4));
    rect(0,H-2,W,1,rgba('#f4a261',0.1));
  };
});