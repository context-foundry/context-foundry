// Scene: Socotra Branch Divergence
// Socotra Island, Yemen
window.CF.register("Socotra Branch Divergence", "Socotra Island, Yemen", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize tree parameters
  var trees=[];
  for(var i=0;i<12;i++){
    trees.push({
      x:Math.random()*W,
      y:H-50-Math.random()*40,
      sway:Math.random()*Math.PI*2,
      swaySpeed:0.02+Math.random()*0.03,
      height:20+Math.random()*10
    });
  }

  // Initialize cloud parameters
  var clouds=[];
  for(var i=0;i<5;i++){
    clouds.push({
      x:Math.random()*W,
      y:Math.random()*40,
      speed:0.1+Math.random()*0.2
    });
  }

  // Initialize limestone plateau points
  var plateauPoints=[];
  for(var x=0;x<W;x+=5){
    plateauPoints.push(Math.sin(x*0.01)*10 + H - 70);
  }

  return function(t){
    // === ALIEN LANDSCAPE ===
    rect(0,0,W,H,rgba('#2d6a4f',1)); // background color

    // === LIMESTONE PLATEAU ===
    for(var x=0;x<plateauPoints.length;x++){
      var height=plateauPoints[x];
      rect(x*5,height,5,20,rgba('#6c757d',0.8));
      // Adding textures to the plateau
      if(Math.random() > 0.5) {
        px(x*5 + 2, height - 5, rgba('#dda15e', 0.5)); // occasional highlights
      }
    }

    // === DRAGON BLOOD TREES ===
    for(var tree of trees){
      // Draw trunk
      rect(tree.x, tree.y, 4, tree.height, '#bc6c25');
      // Draw branches swaying
      for(var j=0;j<3;j++){
        var branchHeight = Math.sin(t*tree.swaySpeed + tree.sway + j) * 5;
        rect(tree.x - 8 + j * 4, tree.y - branchHeight, 4, 10, '#48cae4');
      }
    }

    // === TURQUOISE COAST ===
    rect(0,H-40,W,40,rgba('#48cae4',0.9));
    
    // === CLOUDS ANIMATION ===
    for(var cloud of clouds){
      cloud.x += cloud.speed;
      if(cloud.x > W + 20){
        cloud.x = -20;
        cloud.y = Math.random()*40;
      }
      circle(cloud.x, cloud.y, 10, rgba('#ffffff', 0.6));
      circle(cloud.x + 10, cloud.y, 10, rgba('#ffffff', 0.4));
      circle(cloud.x + 5, cloud.y + 5, 10, rgba('#ffffff', 0.5));
    }

    // === MOONLIGHT GLOW BELOW ===
    for(var y=H-10;y<H;y++){
      var a=1-(y-(H-10))/10;
      rect(0,y,W,1,rgba('#ffffff',a*0.3));
    }

    // REQUIRED: bottom glow line (brand consistency)
    rect(0,H-1,W,1,rgba('#bc6c25',0.3));
    rect(0,H-2,W,1,rgba('#bc6c25',0.1));
  };
});