// Scene: sudo rm -rf /winter
// Lofoten Islands, Norway
window.CF.register("sudo rm -rf /winter", "Lofoten Islands, Norway", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Snow particles
  var snowflakes=[];
  for(var i=0;i<100;i++){
    snowflakes.push({
      x:Math.random()*W, y: Math.random()*H,
      vy:0.5+Math.random()*1.5,
      alpha:0.1+Math.random()*0.5
    });
  }

  // Initialize cabin properties
  var cabinCount = 5;
  var cabins = [];
  var cabinWidth = 30, cabinHeight = 20;
  var colors = ['#ffafcc', '#ffafcc', '#ffc8dd'];
  for(var i=0; i<cabinCount; i++) {
    cabins.push({
      x: 50 + i * (cabinWidth + 20), 
      y: H - 60, 
      color: colors[Math.floor(Math.random() * colors.length)]
    });
  }

  // Initialize mountain properties
  var mountains = [];
  var numMountains = 7;
  for(var i=0; i<numMountains; i++){
    mountains.push({
      x: i * (W / numMountains),
      base: H - 60,
      height: 25 + Math.random() * 40
    });
  }

  return function(t){
    // Sky gradient
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var color=lerp('#bde0fe','#cdb4db', Math.sin(p * Math.PI));
      rect(0,y,W,2,color);
    }

    // Draw mountains
    for(var m of mountains) {
      rect(m.x, m.base-m.height, W/numMountains, m.height, '#a2d2ff');
    }

    // Draw cabins
    for(var cabin of cabins){
      rect(cabin.x, cabin.y, cabinWidth, cabinHeight, cabin.color);
      // Roof
      rect(cabin.x - 5, cabin.y - 10, cabinWidth + 10, 10, '#ff6f61');
    }

    // Draw water reflection
    for(var x=0; x<W; x+=4){
      var waveHeight = Math.sin((x + t * 20) * 0.05) * 2;
      rect(x, H - 10 + waveHeight, 4, 5, rgba('#ffffff', 0.1));
    }

    // Draw still fjord water
    rect(0, H - 5, W, 5, rgba('#bde0fe', 0.5));

    // Animate snowflakes
    for(var s of snowflakes) {
      s.y += s.vy;
      if(s.y > H) {
        s.y = -5;
        s.x = Math.random() * W;
      }
      px(s.x, s.y, rgba('#ffffff', s.alpha));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#ffafcc',0.4));
    rect(0,H-2,W,1,rgba('#ffafcc',0.1));
  };
});