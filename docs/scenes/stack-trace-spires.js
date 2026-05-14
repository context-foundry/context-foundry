// Scene: Stack Trace Spires
// Zhangjiajie National Forest, Hunan, China
window.CF.register("Stack Trace Spires", "Zhangjiajie National Forest, Hunan, China", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Sandstone pillars
  var pillars=[];
  for(var i=0;i<15;i++){
    var baseX = Math.random() * W;
    var height = 50 + Math.random() * 100;
    pillars.push({x: baseX, height: height});
  }

  // Hanging bridges
  var bridges=[];
  for(var j=0;j<5;j++){
    var bridgeX = Math.random() * W;
    bridges.push({x: bridgeX, y: 80 + Math.random() * 40});
  }

  // Pine trees on rocks
  var trees=[];
  for(var k=0;k<20;k++){
    var treeX = Math.random() * W;
    var treeHeight = 10 + Math.random() * 30;
    trees.push({x: treeX, height: treeHeight});
  }

  return function(t){
    // === SKY (y: 0-75) ===
    for(var y=0;y<75;y++){
      var p=y/75;
      rect(0,y,W,1,lerp('#caf0f8','#9bc7e8',p));
    }

    // === MIST BETWEEN PILLS ===
    for(var i=0;i<pillars.length;i++){
      var mistY = pillars[i].height + Math.sin(t*0.5 + i) * 8;
      rect(pillars[i].x - 5, mistY, 10, 10, rgba('#ffffff', 0.2));
    }

    // === SANDSTONE PILLARS ===
    for(var i=0;i<pillars.length;i++){
      var baseY = H - pillars[i].height;
      rect(pillars[i].x - 10, baseY, 20, pillars[i].height, '#6c757d');
    }

    // === HANGING BRIDGES ===
    for(var j=0;j<bridges.length;j++){
      var bridgeY = bridges[j].y;
      rect(bridges[j].x - 30, bridgeY, 60, 5, '#adb5bd');
      rect(bridges[j].x - 2, bridgeY - 2, 4, 4, '#2d6a4f'); // Support
      rect(bridges[j].x - 2, bridgeY - 10, 4, 8, '#2d6a4f'); // Support
    }

    // === PINE TREES ===
    for(var k=0;k<trees.length;k++){
      for(var tY=0;tY<trees[k].height;tY++){
        px(trees[k].x, H - tY - 1, '#40916c');
      }
      px(trees[k].x, H - trees[k].height - 1, '#6c757d'); // Tree top
    }

    // === FOREGROUND DETAILS ===
    for(var i=0;i<pillars.length;i++){
      // Shadow on side of pillars
      var shadowOffset = Math.sin(t + i) * 2;
      rect(pillars[i].x - 10 + shadowOffset, H - pillars[i].height, 20, pillars[i].height, rgba('#2d6a4f', 0.1));
    }

    // === MIST ANIMATION ===
    for(var i=0;i<pillars.length;i++){
      var mistX = pillars[i].x + Math.sin(t * 0.3 + i) * 5;
      rect(mistX - 5, H - pillars[i].height, 10, 10, rgba('#ffffff', 0.1 + osc(t, 0.3, i) * 0.2));
    }

    // REQUIRED: bottom glow line (brand consistency)
    rect(0,H-1,W,1,rgba('#40916c',0.3));
    rect(0,H-2,W,1,rgba('#2d6a4f',0.1));
  };
});