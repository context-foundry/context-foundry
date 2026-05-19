// Scene: 404: Sand Not Found
// White Sands National Park, New Mexico, USA
window.CF.register("404: Sand Not Found", "White Sands National Park, New Mexico, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Yucca plants
  var yuccas=[];
  for(var i=0;i<8;i++){
    yuccas.push({x:Math.random()*W,y:H-30-Math.random()*30});
  }

  // Ripple patterns
  var rippleFrequencies = [];
  for(var i = 0; i < 10; i++) {
    rippleFrequencies.push({frequency: 0.5 + Math.random() * 2, phase: Math.random() * Math.PI});
  }

  // Initialize rising dust particles
  var dustParticles = [];
  for(var i=0;i<50;i++){
    dustParticles.push({
      x:Math.random()*W,
      y:H + Math.random()*20,
      vy:-(Math.random() * 0.4 + 0.1),
      age: 0,
      maxAge: Math.random() * 30 + 10
    });
  }

  return function(t){
    // Sky gradient -- pale blue to beige
    for(var y=0;y<H;y++){
      var p=y/H;
      var col=lerp('#8ecae6', '#f8f9fa', p);
      rect(0,y,W,1,col);
    }

    // Distant San Andres Mountains
    var mountainBaseY = H - 100;
    var mountainColor = '#e9ecef';
    for(var x=0; x<W; x+=4){
      var height = Math.sin(x * 0.05 + t) * 10 + 30;
      rect(x, mountainBaseY - height, 4, height, mountainColor);
    }

    // Draw white gypsum dunes with ripple patterns
    for(var x=0; x<W; x++){
      var ripple = Math.sin((x * 0.02) + (t * 2));
      var duneHeight = Math.max(1, 8 + ripple * 2);
      var duneColor = rgba('#dee2e6', Math.sqrt(duneHeight / 15)); 
      rect(x, H - duneHeight, 1, duneHeight, duneColor);
    }

    // Draw yucca plants
    for(var yucca of yuccas){
      var baseX = yucca.x;
      var baseY = yucca.y;
      rect(baseX - 1, baseY, 3, 10, '#219ebc'); // stem
      for(var j = 0; j < 4; j++){
        px(baseX - 5 + j * 2, baseY - 5, '#8ecae6'); // leaves
        px(baseX + 3 + j * 2, baseY - 5, '#8ecae6');
      }
    }

    // Create ripple patterns in the sand
    for(var freq of rippleFrequencies) {
      for(var x=0; x<W; x+=2){
        var ripple = Math.sin((x * freq.frequency) + (t + freq.phase)) * 0.5;
        px(x, H - 2 + ripple * 2, rgba('#e9ecef', 0.5));
      }
    }

    // Animate dust particles rising
    for(var p of dustParticles){
      if(p.age < p.maxAge){
        px(p.x, p.y, rgba('#f8f9fa', 0.6 - (p.age / p.maxAge) * 0.5));
        p.y += p.vy;
        p.age++;
      } else {
        p.age = 0;
        p.y = H + Math.random() * 20;
        p.x = Math.random() * W;
      }
    }

    // Bottom glow line for brand consistency
    rect(0,H-1,W,1,rgba('#e9ecef',0.3));
    rect(0,H-2,W,1,rgba('#e9ecef',0.1));
  };
});