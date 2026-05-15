// Scene: Autumn Deprecation Notice
// Green Mountain National Forest, Vermont, USA
window.CF.register("Autumn Deprecation Notice", "Green Mountain National Forest, Vermont, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Leaf particles -- persistent array
  var leaves=[];
  for(var i=0;i<100;i++){
    leaves.push({x:Math.random()*W, y:Math.random()*H, vx:0, vy:0, life:0, maxLife:0, color: '#e63946'});
  }

  function emitLeaf(sx, sy){
    for(var l of leaves){
      if(l.life <= 0){
        l.x = sx;
        l.y = sy;
        l.vx = (Math.random() - 0.5) * 1;
        l.vy = Math.random() * 0.5 + 0.5;
        l.maxLife = 40 + Math.random() * 20;
        l.life = l.maxLife;
        l.color = '#e63946';
        break;
      }
    }
  }

  return function(t){
    // Background gradient -- calm autumn sky
    for(var y=0; y<H; y+=2){
      var p = y/H;
      var col = lerp('#264653', '#2a9d8f', p);
      rect(0,y,W,2,col);
    }

    // Canopy
    var canopyHeight = 60;
    for(var x=0; x<W; x+=4){
      for(var y=-10; y<canopyHeight; y+=3){
        px(x + (Math.random() * 10 - 5), (H - 80 + y) + Math.sin(t*0.2 + x * 0.01)*3, '#e63946');
      }
    }

    // Covered bridge
    var bridgeX = W / 2 - 60, bridgeY = H - 120;
    rect(bridgeX, bridgeY, 120, 15, '#f4a261');
    for(var i=0; i<4; i++){
      rect(bridgeX + 10 + i*30, bridgeY - 20, 6, 20, '#2a9d8f');
    }

    // Stone wall beside the path
    var wallY = H - 30;
    for(var i=0; i<W; i+=20){
      rect(i, wallY, 15, 10, '#264653');
      rect(i + 5, wallY + 5, 5, 10, '#f4a261');
    }

    // Leaf-strewn pathway
    for(var i=0; i<W; i+=10){
      rect(i, H - 60, 8, 8, '#f4a261');
    }

    // Emit falling leaves
    if(Math.random() < 0.1) emitLeaf(Math.random() * W, H - 110);

    // Animate leaves
    for(var l of leaves){
      if(l.life > 0){
        l.x += l.vx;
        l.y += l.vy;
        l.life--;
        var a = (l.life / l.maxLife);
        px(l.x, l.y, rgba(l.color, a * 0.8));
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#f4a261',0.3));
    rect(0,H-2,W,1,rgba('#f4a261',0.1));
  };
});