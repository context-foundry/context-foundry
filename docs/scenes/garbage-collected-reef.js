// Scene: Garbage Collected Reef
// Raja Ampat, West Papua, Indonesia
window.CF.register("Garbage Collected Reef", "Raja Ampat, West Papua, Indonesia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Marine fish school particles
  var fishSchool=[];
  for(var i=0;i<30;i++){
    fishSchool.push({
      x:Math.random()*W, 
      y:Math.random()*(H-80), 
      vx:Math.random()*0.5+0.5,
      phase:Math.random()*Math.PI*2,
      size:3+Math.random()*2
    });
  }

  // Manta ray
  var mantaRay = {
    x: 0,
    y: 120,
    width: 30,
    height: 10,
    phase: Math.random() * Math.PI * 2
  };

  // Coral structures
  var corals=[];
  var coralTypes = ['#52b788', '#ffd166', '#ff6b6b'];
  for (var i = 0; i < 50; i++) {
    corals.push({
      x: Math.random() * W,
      y: H - 30 - Math.random() * 50,
      width: 5 + Math.random() * 10,
      height: 10 + Math.random() * 20,
      color: coralTypes[Math.floor(Math.random() * coralTypes.length)]
    });
  }

  return function(t){
    // Background gradient
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#0077b6', '#00b4d8', p);
      rect(0,y,W,2,col);
    }

    // Draw corals
    for(var coral of corals){
      rect(coral.x, coral.y, coral.width, coral.height, coral.color);
    }

    // Draw fish school
    for(var fish of fishSchool){
      fish.x += fish.vx;
      if(fish.x > W) fish.x = 0;
      var fishColor = '#ffffff';
      for(var f=0; f<fish.size; f++){
        px(fish.x + f * 1.5, fish.y + Math.sin(fish.phase + f) * 2, fishColor);
      }
      fish.phase += 0.1;
    }

    // Manta ray movement
    mantaRay.x += 1 + osc(t, 3, mantaRay.phase) * 0.5;
    mantaRay.y = 120 + Math.sin(t + mantaRay.phase) * 5;
    mantaRay.phase += 0.05;

    // Draw manta ray
    rect(mantaRay.x, mantaRay.y, mantaRay.width, mantaRay.height, '#00b4d8');
    circle(mantaRay.x + mantaRay.width / 2, mantaRay.y - 5, 3, '#00b4d8');

    // Karst islands backdrop
    var islandCount = 6;
    for(var i=0; i<islandCount; i++){
      var x = Math.random() * W;
      var y = H - 30 - Math.random() * 50;
      var w = 30 + Math.random() * 50;
      var h = 20 + Math.random() * 20;
      rect(x, y, w, h, '#005b73');
      for (var j = 0; j < 3; j++) {
        px(x + Math.random() * w, y, '#00777a');
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#ffd166',0.4));
    rect(0,H-2,W,1,rgba('#ffd166',0.1));
  };
});