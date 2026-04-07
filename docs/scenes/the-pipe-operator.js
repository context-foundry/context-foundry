// Scene: The Pipe Operator
// Thurston Lava Tube, Hawaii Volcanoes NP, USA
window.CF.register("The Pipe Operator", "Thurston Lava Tube, Hawaii Volcanoes NP, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Dripping particles
  var drips=[];
  for(var i=0;i<50;i++){
    drips.push({x:Math.random()*W, y:0, vy:0, life:0, maxLife:Math.random()*30+10});
  }

  // Ferns
  var ferns=[];
  for(var i=0;i<6;i++){
    ferns.push({x:50+i*60, y:H-180-Math.random()*40});
  }

  // Distant light flicker
  var lightFlicker = srand(123);
  var lightY = H-30 + Math.sin(lightFlicker() * 20) * 10;

  // Ground texture
  var groundTexture = [];
  for(var x=0; x<W; x++) {
    groundTexture[x] = rgba('#343a40', 0.5+(Math.sin(x*0.05)*0.05));
  }

  return function(t){
    // Background gradient -- dark to faint light
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col = p < 0.5 ? lerp('#1d1d1d', '#343a40', p*2) : lerp('#343a40', '#495057', (p-0.5)*2);
      rect(0,y,W,2,col);
    }

    // Lava tube structure
    var tubeTop = H - 120;
    for(var y=tubeTop; y<H; y+=2){
      var p = (y-tubeTop)/(H-tubeTop);
      rect(0,y,W,2,lerp('#1d1d1d', '#495057', p));
    }

    // Fern Entrance
    for(var fern of ferns) {
      rect(fern.x, fern.y, 10, 40, '#52b788');
      for(var leaf=0; leaf<4; leaf++) {
        px(fern.x+leaf, fern.y-10-lean(leaf, 3), '#74c69d');
      }
      for(var leaf=1; leaf<4; leaf++) {
        px(fern.x+leaf, fern.y-20-lean(leaf, 3), '#74c69d');
      }
    }

    // Dripping ceiling
    for(var drip of drips) {
      if(drip.life > 0){
        drip.y += drip.vy;
        drip.x += (Math.sin(t*0.2) * 0.5); 
        drip.life--;
        px(drip.x, drip.y, rgba('#74c69d', 0.5));
      } else {
        drip.y = Math.random() * 10; // Resets at top
        drip.x = Math.random() * W;
        drip.vy = 1 + Math.random() * 2; // Falling speed
        drip.life = drip.maxLife;
      }
    }

    // Distant light source
    rect(0, lightY, W, 1, rgba('#fff', 0.2 + osc(t, 4, 0.5) * 0.3));
    
    // Ground detail
    for(var x=0; x<W; x++){
      rect(x, H-1, 1, 1, groundTexture[x]);
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#52b788',0.3));
    rect(0,H-2,W,1,rgba('#74c69d',0.1));
  };
});

function lean(index, offset) {
  return (index - 3) * offset;
}