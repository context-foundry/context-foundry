// Scene: Edge Case Cliffside
// Cliffs of Moher, County Clare, Ireland
window.CF.register("Edge Case Cliffside", "Cliffs of Moher, County Clare, Ireland", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute cloud formation
  var clouds=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<5;i++){
      clouds.push({
        x:Math.random()*W,
        y:Math.random()*50,
        size:5+r()*10,
        drift:r()*0.5
      });
    }
  })();

  // Pre-compute puffins
  var puffins=[];
  (function(){
    var r=srand(1002);
    for(var i=0;i<10;i++){
      puffins.push({
        x:Math.random() * W,
        y:Math.random() * (H - 50) + 50,
        phase:r()*Math.PI*2,
        bob:r()*2 + 1
      });
    }
  })();

  // O'Brien's Tower state
  var obriensTower = {x:200, y:H-50};

  // Waves state
  var waveOffset = 0;

  return function(t){
    // === SKY ===
    for(var y=0;y<H*0.5;y++){
      var p=y/(H*0.5);
      rect(0,y,W,1,lerp('#6c757d','#48cae4',p));
    }

    // === CLOUDS ===
    for(var cloud of clouds){
      var drift = cloud.drift * Math.sin(t + cloud.x);
      rect(cloud.x + drift, cloud.y, cloud.size, 5, rgba('#ffffff', 0.5));
    }

    // === CLIFF FACE ===
    for(var x=0;x<W;x++){
      var cliffHeight = Math.sin(x * 0.01) * 30 + 200;
      for(var y=cliffHeight; y<H; y++){
        px(x, y, lerp('#344e41','#495057',(y - cliffHeight) / (H - cliffHeight)));
      }
    }

    // === O'BRIEN'S TOWER ===
    rect(obriensTower.x-10, obriensTower.y-30, 20, 30, '#6c757d');
    rect(obriensTower.x-5, obriensTower.y-30, 10, 10, '#ffffff');

    // === PUFFIN ANIMATION ===
    for(var puffin of puffins){
      puffin.y += Math.sin(t * 0.5 + puffin.phase) * puffin.bob;
      circle(puffin.x, puffin.y, 2, '#ffffff');
      circle(puffin.x-2, puffin.y-1, 1, '#000000');
    }

    // === CRASHING WAVES ===
    for(var x=0;x<W;x++){
      var waveHeight = Math.sin(waveOffset + x * 0.05) * 5 + 10;
      for(var y=H - waveHeight; y<H;y++){
        px(x, y, '#48cae4');
      }
    }
    waveOffset += 0.1;

    // REQUIRED: bottom glow line (brand consistency)
    rect(0,H-1,W,1,rgba('#48cae4',0.3));
    rect(0,H-2,W,1,rgba('#344e41',0.1));
  };
});