// Scene: Shipping Code from the Abyss
// Challenger Deep, Mariana Trench
window.CF.register("Shipping Code from the Abyss", "Challenger Deep, Mariana Trench", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Marine snow particles
  var marineSnow=[];
  for(var i=0;i<40;i++){
    marineSnow.push({
      x:Math.random()*W,y:Math.random()*H,
      vy:0.15+Math.random()*0.35,
      vx:(Math.random()-0.5)*0.15,
      alpha:0.1+Math.random()*0.2
    });
  }

  // Bioluminescent flashes
  var bioFlashes=[];
  for(var i=0;i<6;i++){
    bioFlashes.push({
      x:Math.random()*W,y:Math.random()*H,
      life:0,maxLife:15+Math.floor(Math.random()*20),
      col:['#00BFA5','#00E5FF','#00B8D4'][Math.floor(Math.random()*3)]
    });
  }

  // Vent plume particles
  var ventPlume=[];
  for(var i=0;i<30;i++){
    ventPlume.push({x:0,y:0,vx:0,vy:0,life:0,maxLife:40,col:'#FF6D00'});
  }

  function emitVentParticle(sx,sy){
    for(var p of ventPlume){
      if(p.life<=0){
        p.x=sx+(Math.random()-0.5)*4;
        p.y=sy;
        p.vx=(Math.random()-0.5)*0.8;
        p.vy=-0.5-Math.random()*1.5;
        p.maxLife=30+Math.random()*30;
        p.life=p.maxLife;
        var r=Math.random();
        p.col=r>0.6?'#FF6D00':r>0.3?'#D50000':'#3E2723';
        break;
      }
    }
  }

  return function(t){
    // === WATER COLUMN -- full canvas dark gradient ===
    for(var y=0;y<H;y+=2){
      var p=y/H;
      var col;
      if(p<0.4) col=lerp('#050a12','#0a1628',p/0.4);
      else if(p<0.7) col=lerp('#0a1628','#081420',(p-0.4)/0.3);
      else col=lerp('#081420','#060d18',(p-0.7)/0.3);
      rect(0,y,W,2,col);
    }

    // === FAINT LIGHT FROM ABOVE ===
    for(var ray=0;ray<3;ray++){
      var rx=100+ray*150;
      var sway=Math.sin(t*0.2+ray*2)*10;
      for(var y=0;y<100;y++){
        var spread=y*0.2;
        var cx=rx+sway+y*0.1;
        for(var dx=Math.floor(-spread);dx<=Math.ceil(spread);dx++){
          var a=0.025*(1-Math.abs(dx)/Math.max(spread,1))*(1-y/100);
          if(a>0.003) px(cx+dx,y,rgba('#8EC8E8',a));
        }
      }
    }

    // === DEPTH GAUGE (left edge) ===
    for(var y=20;y<=240;y++){
      px(12,y,rgba('#8EC8E8',0.1+osc(t,8,0)*0.05));
    }
    var depths=[{y:20,label:'0m'},{y:75,label:'2,500m'},{y:130,label:'5,000m'},{y:185,label:'8,000m'},{y:240,label:'10,994m'}];
    for(var d of depths){
      rect(8,d.y,8,1,rgba('#8EC8E8',0.15));
      ctx.save();
      ctx.globalAlpha=0.15+osc(t,10,d.y*0.01)*0.05;
      ctx.fillStyle='#8EC8E8';
      ctx.font='6px monospace';
      ctx.textBaseline='middle';
      ctx.fillText(d.label,18,d.y);
      ctx.restore();
    }

    // === OCEAN FLOOR ===
    var floorY=H-25;
    for(var x=0;x<W;x++){
      var fh=25+Math.sin(x*0.04)*3+Math.sin(x*0.12)*1.5;
      for(var y=H-fh;y<H;y++){
        var p=(y-(H-fh))/fh;
        px(x,y,lerp('#0d1018','#1a1a2a',p*0.5));
      }
    }
    var floorR=srand(6006);
    for(var i=0;i<80;i++){
      var rx2=Math.floor(floorR()*W);
      var ry2=H-5-Math.floor(floorR()*18);
      px(rx2,ry2,rgba('#252535',0.3+floorR()*0.3));
    }

    // === HYDROTHERMAL VENT (center-right) ===
    var ventX=310, ventBase=H-22;
    var chimneyR=srand(7007);
    for(var y=0;y<48;y++){
      var w=6+Math.floor(Math.sin(y*0.3)*2)+(y<10?3:0);
      for(var dx=-w;dx<=w;dx++){
        var rough=chimneyR()>0.85?'#303040':'#1a1a2a';
        px(ventX+dx,ventBase-y,y<3?'#252535':rough);
      }
    }
    var ventGlow=0.4+osc(t,2,0)*0.4;
    for(var dx=-4;dx<=4;dx++){
      px(ventX+dx,ventBase-48,rgba('#FF6D00',ventGlow));
      px(ventX+dx,ventBase-49,rgba('#D50000',ventGlow*0.6));
    }
    for(var dx=-20;dx<=20;dx++){
      var d=Math.abs(dx);
      if(d<20){
        var a=0.06*(1-d/20)*ventGlow;
        for(var dy=0;dy<5;dy++){
          px(ventX+dx,ventBase+dy,rgba('#FF6D00',a*(1-dy*0.15)));
        }
      }
    }

    // Mineral deposits around base
    var minR=srand(8008);
    for(var i=0;i<30;i++){
      var mx=ventX-15+Math.floor(minR()*30);
      var my=ventBase-Math.floor(minR()*5);
      px(mx,my,minR()>0.5?rgba('#FFB300',0.3):'#ECEFF1');
    }

    // Emit plume particles
    if(Math.random()>0.5) emitVentParticle(ventX,ventBase-50);
    for(var p of ventPlume){
      if(p.life>0){
        p.x+=p.vx;
        p.y+=p.vy;
        p.vx+=(Math.random()-0.5)*0.1;
        p.life--;
        var a=(p.life/p.maxLife)*0.6;
        px(p.x,p.y,rgba(p.col,a));
        if(a>0.3) px(p.x+1,p.y,rgba(p.col,a*0.4));
      }
    }

    // === TUBE WORMS (around vent base) ===
    function drawTubeWorm(wx,wy,h){
      for(var i=0;i<h;i++){
        px(wx,wy-i,'#E0E0E0');
        if(i%3===0) px(wx+1,wy-i,rgba('#BDBDBD',0.5));
      }
      var sway=Math.sin(t*1.5+wx*0.3)*1.5;
      px(wx+sway,wy-h,'#F44336');
      px(wx+sway,wy-h-1,'#E53935');
      px(wx+sway+1,wy-h,'#EF5350');
    }
    drawTubeWorm(295,ventBase,14);
    drawTubeWorm(298,ventBase-1,18);
    drawTubeWorm(301,ventBase,12);
    drawTubeWorm(318,ventBase,16);
    drawTubeWorm(322,ventBase-1,20);
    drawTubeWorm(325,ventBase,13);
    drawTubeWorm(328,ventBase,15);
    drawTubeWorm(332,ventBase-2,11);

    // === ANGLERFISH (left of center) ===
    var anglerBaseX=140, anglerBaseY=160;
    var anglerDrift=Math.sin(t*0.4)*4;
    var ax=anglerBaseX+anglerDrift, ay=anglerBaseY+Math.sin(t*0.3+1)*2;

    for(var dy=-6;dy<=6;dy++){
      var bw=dy<-3?6+dy:dy>3?6-(dy-3):10;
      for(var dx=-bw;dx<=bw;dx++){
        px(ax+dx,ay+dy,'#1a1a2a');
      }
    }
    for(var dx=-7;dx<=5;dx++){
      px(ax+dx,ay+4,rgba('#252540',0.5));
      px(ax+dx,ay+5,rgba('#252540',0.3));
    }

    // Jaw with teeth
    for(var dx=-8;dx<=6;dx++){
      px(ax+dx,ay+6,'#1a1a2a');
      px(ax+dx,ay+7,'#151528');
    }
    for(var i=-7;i<=5;i+=2){
      px(ax+i,ay+5,'#BDBDBD');
    }
    for(var i=-6;i<=4;i+=3){
      px(ax+i,ay+8,'#9E9E9E');
    }

    // Eye
    px(ax+5,ay-2,'#4FC3F7');

    // Dorsal fin
    for(var i=0;i<4;i++){
      px(ax-2+i,ay-6-i,'#151528');
    }

    // Tail
    px(ax-11,ay-1,'#151528');
    px(ax-12,ay-2,'#151528');
    px(ax-12,ay,'#151528');
    px(ax-13,ay-3,'#151528');
    px(ax-13,ay+1,'#151528');

    // Bioluminescent lure
    var lureSwayX=Math.sin(t*1.2)*2;
    var lureSwayY=Math.sin(t*1.8+0.5)*1;
    px(ax+5,ay-4,'#252540');
    px(ax+6+lureSwayX*0.3,ay-6,'#252540');
    px(ax+7+lureSwayX*0.6,ay-8,'#252540');
    var lureGlow=0.5+osc(t,1.5,0)*0.5;
    var lx=ax+8+lureSwayX, ly=ay-10+lureSwayY;
    circle(lx,ly,2,rgba('#00E5FF',lureGlow*0.3));
    px(lx,ly,rgba('#00E5FF',lureGlow));
    px(lx,ly-1,rgba('#B2EBF2',lureGlow*0.6));
    for(var dy=-4;dy<=4;dy++){
      for(var dx=-4;dx<=4;dx++){
        var d=Math.sqrt(dx*dx+dy*dy);
        if(d>1.5&&d<4){
          px(lx+dx,ly+dy,rgba('#00E5FF',0.04*lureGlow*(4-d)/2.5));
        }
      }
    }

    // === JELLYFISH (upper area) ===
    function drawJelly(jx,jy,bellR,col,phase){
      var drift=Math.sin(t*0.3+phase)*8;
      var pulse=Math.sin(t*1.5+phase);
      var bellW=bellR+pulse*1.5;
      var jxA=jx+drift, jyA=jy+Math.sin(t*0.2+phase+1)*5;

      for(var dy=-bellR;dy<=1;dy++){
        var rowW=Math.sqrt(Math.max(0,bellW*bellW-dy*dy));
        for(var dx=-rowW;dx<=rowW;dx++){
          var d=Math.sqrt(dx*dx+dy*dy)/bellW;
          var a=0.12+0.08*(1-d);
          var edgeGlow=d>0.7?0.15*(d-0.7)/0.3:0;
          px(jxA+dx,jyA+dy,rgba(col,a+edgeGlow));
        }
      }

      for(var ti=0;ti<5;ti++){
        var tentX=jxA-bellR*0.6+ti*(bellR*1.2/4);
        for(var ty=0;ty<18;ty++){
          var sway=Math.sin(t*2+ti*0.8+ty*0.4)*2;
          var ta=0.15-ty*0.006;
          if(ta>0) px(tentX+sway,jyA+2+ty,rgba(col,ta));
        }
      }
    }
    drawJelly(80,55,5,'#80DEEA',0);
    drawJelly(380,40,6,'#CE93D8',2.5);

    // === SMALL CREATURES ===
    for(var i=0;i<3;i++){
      var ampX=280+i*25+Math.sin(t*1.5+i*2)*6;
      var ampY=H-35+Math.sin(t*2+i)*3;
      rect(ampX,ampY,3,1,rgba('#90A4AE',0.2));
      px(ampX+3,ampY-1,rgba('#90A4AE',0.15));
    }
    var snailX=200+Math.sin(t*0.25)*30;
    var snailY=190+Math.sin(t*0.35)*5;
    for(var dx=-3;dx<=3;dx++){
      var bh=dx<-1?1:dx>1?1:2;
      for(var dy=-bh;dy<=0;dy++){
        px(snailX+dx,snailY+dy,rgba('#B0BEC5',0.12));
      }
    }
    px(snailX-4,snailY-1,rgba('#B0BEC5',0.08));
    px(snailX-5,snailY,rgba('#B0BEC5',0.05));

    // === MARINE SNOW ===
    for(var s of marineSnow){
      s.y+=s.vy;
      s.x+=s.vx+Math.sin(t*0.5+s.x*0.02)*0.1;
      if(s.y>H+5){
        s.y=-5;
        s.x=Math.random()*W;
      }
      px(s.x,s.y,rgba('#ffffff',s.alpha));
    }

    // === BIOLUMINESCENT FLASHES ===
    for(var f of bioFlashes){
      if(f.life>0){
        f.life--;
        var a=(f.life/f.maxLife);
        var peak=a>0.5?(1-a)*2:a*2;
        circle(f.x,f.y,1,rgba(f.col,peak*0.4));
        px(f.x,f.y,rgba(f.col,peak*0.7));
        for(var d=2;d<5;d++){
          var ha=peak*0.05*(5-d)/3;
          px(f.x+d,f.y,rgba(f.col,ha));
          px(f.x-d,f.y,rgba(f.col,ha));
          px(f.x,f.y+d,rgba(f.col,ha));
          px(f.x,f.y-d,rgba(f.col,ha));
        }
      } else if(Math.random()>0.97){
        f.x=30+Math.random()*(W-60);
        f.y=20+Math.random()*(H-60);
        f.life=f.maxLife;
      }
    }

    // Bottom glow line -- deep abyss
    rect(0,H-1,W,1,rgba('#0a1628',0.6));
    rect(0,H-2,W,1,rgba('#00E5FF',0.04));
  };
});
