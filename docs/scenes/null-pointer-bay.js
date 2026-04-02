// Scene: Null Pointer Bay
// Mosquito Bay, Vieques, Puerto Rico
window.CF.register("Null Pointer Bay", "Mosquito Bay, Vieques, Puerto Rico", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Dinoflagellate particles
  var dinoflagellates=[];
  for(var i=0;i<100;i++){
    dinoflagellates.push({
      x:Math.random()*W, 
      y:Math.random()*H, 
      radius:1+Math.random()*2, 
      life:Math.floor(Math.random()*80)+40
    });
  }

  // Mangrove coordinates
  var mangroves=[
    {x:60, y:H-40}, {x:120, y:H-38}, {x:180, y:H-45}, 
    {x:300, y:H-42}, {x:360, y:H-39}, {x:400, y:H-46}
  ];
  
  // Kayak position
  var kayakX = 240;

  return function(t){
    // Background gradient (night sky fading into dark ocean)
    for(var y=0;y<H;y++){
      var p=y/H;
      var col=lerp('#0b0c2a', '#1a1a5e', p);
      rect(0,y,W,1,col);
    }

    // Ocean surface
    for(var y=110;y<150;y++){
      for(var x=0;x<W;x++){
        var wave=0.2 * Math.sin(x*0.05 + t*2);
        var col=lerp('#001f3f', '#00e5ff', (y-110)/40 + wave);
        px(x,y,col);
      }
    }

    // Mangrove trees
    for(var m of mangroves){
      var trunkHeight = 20 + osc(t + m.x * 0.1, 1, 0) * 10;
      rect(m.x, m.y, 10, -trunkHeight, '#4E342E');
      for(var i=-4; i<=4; i+=2){
        px(m.x + i, m.y - trunkHeight - 1, '#2E7D32');
      }
    }

    // Kayak silhouette
    rect(kayakX,H-55,30,10,'#1a1a5e');
    rect(kayakX + 5, H-50, 20, 3, '#000000');

    // Dinoflagellates glow effect
    for(var d of dinoflagellates){
      if(d.life > 0){
        d.life--;
        d.y += -1 + Math.random() * 2; // Floating effect
        var glowAlpha = (d.life / 80) * 0.5;
        circle(d.x, d.y, d.radius, rgba('#00ff88', glowAlpha));
      } else {
        // Respawn the dinoflagellate
        d.x = Math.random()*W;
        d.y = H + Math.random()*50; // Start from below the canvas
        d.life = Math.floor(Math.random()*80)+40;
      }
    }

    // Star reflections
    for(var i=0; i<50; i++){
      var starX = Math.random() * W;
      var starY = Math.random() * 40;
      var sparkle = osc(t, 5 + Math.random()*5, i) * 0.6;
      if (sparkle > 0.3){
        px(starX, starY, rgba('#ffffff', sparkle));
        px(starX, starY + 1, rgba('#ffffff', sparkle * 0.5));
      }
    }    

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#00e5ff',0.3));
    rect(0,H-2,W,1,rgba('#1a1a5e',0.15));
  };
});