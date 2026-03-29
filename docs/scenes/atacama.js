// Scene: Every Commit Reaches the Stars
// ALMA Observatory, Atacama Desert, Chile
window.CF.register("Every Commit Reaches the Stars", "ALMA Observatory, Atacama Desert, Chile", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute star field
  var stars=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<250;i++){
      stars.push({
        x:Math.floor(r()*W),y:Math.floor(r()*195),
        size:r()>0.97?2:(r()>0.7?1:1),
        baseAlpha:0.1+r()*0.8,
        period:1.5+r()*5,phase:r()*Math.PI*2,
        inBand:false
      });
    }
    for(var i=0;i<150;i++){
      var p=r();
      var centerX=p*W;
      var centerY=170-p*150;
      var spread=(r()+r()+r()-1.5)*40;
      var angle=Math.atan2(-150,W);
      var perpX=Math.sin(angle)*spread;
      var perpY=-Math.cos(angle)*spread;
      var sx=Math.floor(centerX+perpX);
      var sy=Math.floor(centerY+perpY);
      if(sx>=0&&sx<W&&sy>=0&&sy<195){
        stars.push({
          x:sx,y:sy,
          size:r()>0.95?2:1,
          baseAlpha:0.15+r()*0.6,
          period:1.5+r()*5,phase:r()*Math.PI*2,
          inBand:true
        });
      }
    }
  })();

  // Pre-compute nebula wisps
  var nebulaWisps=[];
  (function(){
    var r=srand(2002);
    var colors=['#4A148C','#1A237E','#880E4F','#311B92','#4A148C'];
    for(var w=0;w<5;w++){
      var p=0.2+r()*0.6;
      var cx=p*W;
      var cy=170-p*150+(r()-0.5)*30;
      var pts=[];
      for(var i=0;i<20+Math.floor(r()*15);i++){
        pts.push({
          dx:Math.floor((r()-0.5)*25),
          dy:Math.floor((r()-0.5)*15),
          a:0.03+r()*0.05
        });
      }
      nebulaWisps.push({cx:cx,cy:cy,pts:pts,col:colors[w]});
    }
  })();

  // Satellite state
  var satX=-20, satY=30+Math.random()*40, satVx=0.4+Math.random()*0.3, satVy=0.05+Math.random()*0.1;

  return function(t){
    // === SKY -- ultra dark ===
    for(var y=0;y<195;y++){
      var p=y/195;
      rect(0,y,W,1,lerp('#050510','#0a0a20',p));
    }

    // === MILKY WAY NEBULA TINTING ===
    var coreCx=W*0.5, coreCy=60;
    for(var dy=-25;dy<=25;dy++){
      for(var dx=-35;dx<=35;dx++){
        var d=Math.sqrt((dx*dx)/(35*35)+(dy*dy)/(25*25));
        if(d<1){
          var a=0.03*(1-d);
          px(coreCx+dx,coreCy+dy,rgba('#FF8F00',a));
        }
      }
    }

    // Nebula wisps
    for(var w of nebulaWisps){
      var pulse=0.7+osc(t,8+w.cx*0.01,w.cy*0.05)*0.6;
      for(var p of w.pts){
        px(w.cx+p.dx,w.cy+p.dy,rgba(w.col,p.a*pulse));
      }
    }

    // === STARS ===
    for(var s of stars){
      var twinkle=osc(t,s.period,s.phase);
      var a=s.baseAlpha*0.3+s.baseAlpha*0.7*twinkle;
      var col=s.inBand&&twinkle>0.8?'#FFF9C4':'#e6edf3';
      if(s.size===2){
        rect(s.x,s.y,2,2,rgba(col,a*0.5));
        px(s.x,s.y,rgba(col,a));
        px(s.x+1,s.y,rgba(col,a*0.7));
      } else {
        px(s.x,s.y,rgba(col,a));
      }
    }

    // === SHOOTING STAR ===
    var shootCycle=t%12;
    if(shootCycle<1.2){
      var sp=shootCycle/1.2;
      var ssx=30+sp*400;
      var ssy=10+sp*80;
      rect(ssx,ssy,2,1,rgba('#ffffff',0.9*(1-sp*0.4)));
      for(var ti=1;ti<12;ti++){
        var ta=Math.max(0,(0.7-ti*0.06)*(1-sp*0.3));
        px(ssx-ti*3,ssy-ti*0.6,rgba('#e6edf3',ta));
        if(ti<5) px(ssx-ti*3,ssy-ti*0.6-1,rgba('#FFF9C4',ta*0.4));
      }
    }

    // === SATELLITE ===
    satX+=satVx;
    if(satX>W+20){satX=-20;satY=20+Math.random()*60;satVx=0.4+Math.random()*0.3;satVy=(Math.random()-0.5)*0.1;}
    satY+=satVy;
    px(satX,satY,rgba('#e6edf3',0.6));

    // === HORIZON GLOW ===
    for(var y=180;y<195;y++){
      var glowA=0.04*(195-y)/15;
      rect(0,y,W,1,rgba('#FF6F00',glowA));
    }

    // === DESERT HORIZON & FLOOR ===
    var terrR=srand(3003);
    var terrain=[];
    for(var x=0;x<W;x++){
      terrain[x]=190+Math.sin(x*0.02)*3+Math.sin(x*0.07)*1.5;
    }
    for(var x=0;x<W;x++){
      var ty=Math.floor(terrain[x]);
      for(var y=ty;y<H;y++){
        var p=(y-ty)/(H-ty);
        px(x,y,lerp('#1A1207','#2D1F0E',p));
      }
    }
    var desR=srand(4004);
    for(var i=0;i<100;i++){
      var dx=Math.floor(desR()*W);
      var baseY=Math.floor(terrain[Math.min(dx,W-1)])+1;
      var dy=baseY+Math.floor(desR()*(H-baseY));
      px(dx,dy,rgba('#3E2723',0.2+desR()*0.3));
    }

    // === CACTI SILHOUETTES ===
    function drawCactus(cx,cy,h){
      for(var i=0;i<h;i++){
        px(cx,cy-i,'#0a0808');
        px(cx+1,cy-i,'#0a0808');
      }
      var armH=Math.floor(h*0.4);
      var armY=cy-Math.floor(h*0.6);
      for(var i=0;i<4;i++) px(cx-1-i,armY,'#0a0808');
      for(var i=0;i<armH;i++) px(cx-4,armY-i,'#0a0808');
      var armY2=cy-Math.floor(h*0.45);
      for(var i=0;i<3;i++) px(cx+2+i,armY2,'#0a0808');
      for(var i=0;i<Math.floor(armH*0.7);i++) px(cx+4,armY2-i,'#0a0808');
    }
    drawCactus(60,Math.floor(terrain[60]),20);
    drawCactus(420,Math.floor(terrain[420]),24);
    drawCactus(450,Math.floor(terrain[450]),16);

    // Rocky outcroppings
    function drawRock(rx,ry,w,h){
      for(var dy=0;dy<h;dy++){
        var rw=w-dy*0.5;
        for(var dx=-rw/2;dx<rw/2;dx++){
          px(rx+dx,ry-dy,'#0d0a06');
        }
      }
    }
    drawRock(100,Math.floor(terrain[100]),12,6);
    drawRock(340,Math.floor(terrain[340]),8,4);

    // === ALMA RADIO TELESCOPES ===
    function drawDish(dx,dy,tilt){
      rect(dx-1,dy,3,8,'#78909C');
      rect(dx-2,dy+8,5,2,'#90A4AE');
      var tiltOff=Math.sin(t*0.3+tilt)*0.5;
      for(var i=-6;i<=6;i++){
        var curve=Math.floor(i*i*0.15)+tiltOff;
        px(dx+i,dy-2-curve,'#B0BEC5');
        px(dx+i,dy-1-curve,'#90A4AE');
      }
      px(dx,dy-5,'#CFD8DC');
      px(dx,dy-6,'#ECEFF1');
    }
    drawDish(150,Math.floor(terrain[150])-2,0);
    drawDish(200,Math.floor(terrain[200])-2,2);
    drawDish(260,Math.floor(terrain[260])-2,4);

    // === PERSON WITH TELESCOPE ===
    var px2=380, py2=Math.floor(terrain[380]);
    circle(px2,py2-6,1,'#050510');
    rect(px2-1,py2-4,3,4,'#050510');
    px(px2-1,py2,'#050510');
    px(px2+1,py2,'#050510');
    for(var i=0;i<8;i++){
      px(px2+2+i,py2-5-i*1.2,'#050510');
    }
    px(px2+4,py2-3,'#050510');
    px(px2+3,py2-1,'#050510');
    px(px2+5,py2-1,'#050510');

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#FF6F00',0.15));
    rect(0,H-2,W,1,rgba('#FF8F00',0.05));
  };
});
