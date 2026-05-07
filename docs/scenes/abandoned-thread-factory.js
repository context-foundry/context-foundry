// Scene: Abandoned Thread Factory
// Pripyat, Chernobyl Exclusion Zone, Ukraine
window.CF.register("Abandoned Thread Factory", "Pripyat, Chernobyl Exclusion Zone, Ukraine", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Initialize persistent state
  var weeds=[];
  var weedCount=100;
  var sigCount=10;
  for(var i=0;i<weedCount;i++){
    weeds.push({x:Math.random()*W, y:H-60+Math.random()*40, h:5+Math.random()*15});
  }

  // Produce radiation signs
  var signs=[];
  var signPattern=['#FF0000', '#FFFF00', '#000000'];
  for(var j=0;j<sigCount;j++){
    signs.push({x:Math.random()*W, y:Math.random()*(H-70), phase:Math.random()*Math.PI*2});
  }

  return function(t){
    // Background gradient - urban decay
    for(var y=0; y<H; y+=2){
      var p = y/H;
      var col = lerp('#6c757d', '#343a40', p);
      rect(0, y, W, 2, col);
    }

    // Cracked building
    rect(50, H-100, 40, 60, '#495057');
    for(var y=H-100; y<H-40; y+=10){
      for(var x=50; x<90; x+=5){
        if(Math.random()>0.5){
          px(x, y, '#adb5bd');
        }
      }
    }
    // Windows
    for(var wx=55; wx<80; wx+=10){
      for(var wy=H-80; wy<H-60; wy+=10){
        px(wx, wy, '#2d6a4f');
      }
    }

    // Overgrown ferris wheel
    var wheelRadius=40;
    var wheelX=W/2, wheelY=H-60;
    for(var angle=0; angle<Math.PI*2; angle+=0.2){
      var x=wheelX + Math.cos(angle) * wheelRadius;
      var y=wheelY + Math.sin(angle) * wheelRadius;
      px(Math.round(x), Math.round(y), '#adb5bd');
      if(Math.random() < 0.2) {
        circle(Math.round(x), Math.round(y), 2, '#2d6a4f');
      }
    }
    // Seats on wheel
    for(var i=0; i<8; i++){
      var seatX=wheelX + Math.cos(i*Math.PI/4) * (wheelRadius-10);
      var seatY=wheelY + Math.sin(i*Math.PI/4) * (wheelRadius-10);
      px(Math.round(seatX), Math.round(seatY), '#6c757d');
    }

    // Nature reclaiming buildings
    for(var weed of weeds){
      for(var i=0; i<weed.h; i++){
        px(weed.x, weed.y-i, '#2d6a4f');
      }
    }

    // Radiation signs
    for(var sign of signs){
      var x=sign.x, y=sign.y;
      rect(x-3, y-8, 6, 6, rgba(signPattern[0], 0.8));
      rect(x-5, y-8, 1, 10, signPattern[1]);
      rect(x+4, y-8, 1, 10, signPattern[1]);
      px(x, y, signPattern[2]);
    }

    // Foreground detail - shadows of grass
    for(var weed of weeds){
      for(var i=0; i<weed.h; i++){
        px(weed.x, H-60-i, rgba('#2d6a4f', 0.5));
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#FF0000',0.3));
    rect(0,H-2,W,1,rgba('#FF0000',0.1));
  };
});