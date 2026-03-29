// Scene: The Foundry (original)
// Where code is forged into commits
window.CF.register("The Foundry", "", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Spark particles -- persistent array
  var sparks=[];
  for(var i=0;i<60;i++){
    sparks.push({x:0,y:0,vx:0,vy:0,life:0,maxLife:0,hue:0});
  }
  function emitSpark(sx,sy){
    for(var s of sparks){
      if(s.life<=0){
        s.x=sx;s.y=sy;
        s.vx=(Math.random()-0.5)*3;
        s.vy=-Math.random()*4-1;
        s.maxLife=20+Math.random()*40;
        s.life=s.maxLife;
        s.hue=Math.random();
        break;
      }
    }
  }

  return function(t){
    // Sky gradient -- deep dark with warm horizon glow
    for(var y=0;y<H;y+=2){
      var p=y/H;
      var col=p<0.5?lerp('#08090c','#0d1117',p/0.5):lerp('#0d1117','#1a1208',(p-0.5)/0.5);
      rect(0,y,W,2,col);
    }

    // Distant city skyline silhouette
    var sr=srand(42);
    for(var i=0;i<20;i++){
      var bx=i*24+Math.floor(sr()*8)-4;
      var bh=15+Math.floor(sr()*50);
      var by=H-60-bh;
      rect(bx,by,14+Math.floor(sr()*10),bh,'#0a0c10');
      for(var wy=by+4;wy<by+bh-4;wy+=6){
        for(var wx=bx+2;wx<bx+12;wx+=4){
          if(sr()>0.6){
            px(wx,wy,rgba('#f0a500',0.05+sr()*0.1));
            px(wx+1,wy,rgba('#f0a500',0.03+sr()*0.06));
          }
        }
      }
    }

    // Ground plane
    rect(0,H-60,W,60,'#0a0c10');
    rect(0,H-60,W,1,rgba('#f0a500',0.15));
    var gr=srand(200);
    for(var i=0;i<80;i++){px(Math.floor(gr()*W),H-59+Math.floor(gr()*58),rgba('#161b22',0.3+gr()*0.2));}

    // THE FOUNDRY (center) -- anvil + crucible
    var fx=W/2, fy=H-60;

    // Foundry structure -- dark arch
    rect(fx-60,fy-80,120,80,'#10131a');
    for(var x=-50;x<=50;x++){
      var ah=Math.sqrt(2500-x*x)*0.6;
      rect(fx+x,fy-80-ah,1,ah,'#10131a');
    }
    for(var x=-52;x<=52;x++){
      var ah=Math.sqrt(2704-Math.min(x*x,2704))*0.6;
      px(fx+x,fy-80-ah,rgba('#f0a500',0.2));
    }

    // Crucible
    var crx=fx-35, cry=fy-20;
    rect(crx,cry,20,18,'#2a1a0a');
    rect(crx+1,cry+1,18,16,'#1a100a');
    for(var x=0;x<16;x++){
      var mh=2+Math.round(osc(t,1.5+x*0.1,x*0.5)*3);
      var glow=osc(t,2,x*0.3);
      rect(crx+2+x,cry+2,1,mh,rgba('#f0a500',0.4+glow*0.4));
      if(glow>0.6)rect(crx+2+x,cry+1,1,1,rgba('#ffcc44',0.3));
    }
    for(var y=0;y<15;y++){
      var gw=8-y*0.4;
      if(gw>0)rect(crx+10-gw/2,cry-y,gw,1,rgba('#f0a500',0.06*(15-y)/15));
    }

    // Anvil
    var ax=fx-8, ay=fy-12;
    rect(ax,ay,16,4,'#3a3a44');
    rect(ax-2,ay,2,4,'#2a2a34');
    rect(ax+16,ay,4,3,'#2a2a34');
    rect(ax+2,ay+4,12,8,'#2a2a34');
    rect(ax+4,ay+12,8,2,'#3a3a44');

    // Glowing code block on anvil
    var glow=osc(t,3,0);
    rect(ax+3,ay-4,10,4,rgba('#f0a500',0.3+glow*0.5));
    rect(ax+4,ay-3,8,2,rgba('#ffcc44',0.2+glow*0.4));
    rect(ax+4,ay-3,3,1,rgba('#ff7b72',0.4+glow*0.3));
    rect(ax+8,ay-3,3,1,rgba('#79c0ff',0.3+glow*0.3));
    rect(ax+5,ay-2,5,1,rgba('#3fb950',0.3+glow*0.2));

    // Hammer
    var hammerPhase=t%3;
    var hammerUp=hammerPhase<2?hammerPhase*8:16-(hammerPhase-2)*16;
    var hx=fx+6, hy=ay-10-hammerUp;
    rect(hx,hy,4,8,'#5a5a64');
    rect(hx-2,hy-4,8,4,'#6a6a74');
    rect(hx-1,hy-3,6,2,'#8a8a94');

    if(hammerPhase>2.8&&hammerPhase<2.95){
      for(var i=0;i<5;i++)emitSpark(ax+8,ay-4);
    }

    // Output stream
    for(var i=0;i<6;i++){
      var ox=fx+50+i*25+(t*8)%25;
      var oy=fy-15+Math.sin(ox*0.05+t)*3;
      var fade=Math.max(0,1-(ox-(fx+50))/150);
      if(ox<fx+200){
        rect(ox,oy,8,3,rgba('#3fb950',0.15+fade*0.25));
        rect(ox+1,oy+1,6,1,rgba('#3fb950',0.1+fade*0.15));
      }
    }

    // Input stream
    for(var i=0;i<6;i++){
      var ix=fx-200+i*25+(t*6)%25;
      var iy=fy-20+Math.sin(ix*0.04+t*0.7)*4;
      var fade=Math.max(0,(ix-(fx-200))/150);
      if(ix<fx-50&&ix>fx-200){
        rect(ix,iy,10,2,rgba('#8b949e',0.1+fade*0.2));
        rect(ix+2,iy,4,1,rgba('#f0a500',0.05+fade*0.1));
      }
    }

    // Sparks
    for(var s of sparks){
      if(s.life>0){
        s.x+=s.vx;s.y+=s.vy;
        s.vy+=0.1;
        s.life--;
        var a=(s.life/s.maxLife);
        var col=s.hue>0.5?'#f0a500':'#ffcc44';
        px(s.x,s.y,rgba(col,a*0.8));
        if(a>0.5)px(s.x,s.y-1,rgba(col,a*0.3));
      }
    }
    if(Math.random()>0.7)emitSpark(crx+5+Math.random()*10,cry);

    // Pipeline labels
    var labels=[
      {x:fx-170,y:fy-40,c:'#8b949e',a:0.2},
      {x:fx+120,y:fy-40,c:'#3fb950',a:0.2},
    ];
    for(var l of labels){
      for(var i=0;i<4;i++){
        rect(l.x+i*6,l.y,4,1,rgba(l.c,l.a+osc(t,4,i)*0.1));
      }
    }

    // Stars
    var str=srand(99);
    for(var i=0;i<60;i++){
      var sx=Math.floor(str()*W);
      var sy=Math.floor(str()*90);
      var a=0.1+osc(t,2+str()*4,i*1.3)*0.4;
      var sz=str()>0.9?2:1;
      rect(sx,sy,sz,sz,rgba('#e6edf3',a));
    }

    // Moon
    var mx=W-120, my=28;
    for(var dy=-10;dy<=10;dy++){
      for(var dx=-10;dx<=10;dx++){
        var d=Math.sqrt(dx*dx+dy*dy);
        if(d<=10){
          var a=d<8?0.7:0.7*(10-d)/2;
          rect(mx+dx,my+dy,1,1,rgba('#e6edf3',a));
        }
        if(d<=10){
          var sd=Math.sqrt((dx+5)*(dx+5)+(dy-1)*(dy-1));
          if(sd<9)rect(mx+dx,my+dy,1,1,rgba('#08090c',0.85));
        }
      }
    }
    for(var dy=-16;dy<=16;dy++){
      for(var dx=-16;dx<=16;dx++){
        var d=Math.sqrt(dx*dx+dy*dy);
        if(d>10&&d<16){
          rect(mx+dx,my+dy,1,1,rgba('#e6edf3',0.02*(16-d)/6));
        }
      }
    }

    // Shooting star
    var shootCycle=t%18;
    if(shootCycle<1.5){
      var sp=shootCycle/1.5;
      var ssx=80+sp*350;
      var ssy=8+sp*55;
      rect(ssx,ssy,2,1,rgba('#ffffff',0.8*(1-sp*0.5)));
      for(var ti=1;ti<8;ti++){
        var ta=Math.max(0,(0.6-ti*0.08)*(1-sp*0.3));
        px(ssx-ti*3,ssy-ti*0.8,rgba('#e6edf3',ta));
        if(ti<4)px(ssx-ti*3-1,ssy-ti*0.8,rgba('#f0a500',ta*0.5));
      }
    }

    // Drone
    var droneX=(t*5)%((W+100))-50;
    var droneY=22+Math.sin(t*0.3)*4;
    rect(droneX,droneY,6,2,'#21262d');
    rect(droneX+1,droneY-1,4,1,'#21262d');
    var rotorSpin=Math.floor(t*8)%2;
    rect(droneX-2+rotorSpin,droneY-2,3,1,rgba('#8b949e',0.4));
    rect(droneX+5-rotorSpin,droneY-2,3,1,rgba('#8b949e',0.4));
    if(Math.floor(t*3)%2===0){
      px(droneX,droneY,rgba('#f85149',0.7));
      px(droneX+5,droneY,rgba('#3fb950',0.7));
    }
    if(Math.floor(t*2)%4===0)px(droneX+3,droneY+2,rgba('#ffffff',0.6));

    // UFO
    var ufoPhase=t%45;
    if(ufoPhase>35){
      var up=(ufoPhase-35)/10;
      var ux=W-80-up*400;
      var uy=12+Math.sin(up*8)*2;
      rect(ux-1,uy,8,2,'#30363d');
      rect(ux+1,uy-1,4,1,'#3a3a44');
      rect(ux,uy+2,6,1,'#30363d');
      rect(ux+2,uy-2,2,1,rgba('#79c0ff',0.5));
      var lightPhase=Math.floor(t*6)%3;
      px(ux+1,uy+2,rgba('#f0a500',lightPhase===0?0.7:0.15));
      px(ux+3,uy+2,rgba('#3fb950',lightPhase===1?0.7:0.15));
      px(ux+5,uy+2,rgba('#79c0ff',lightPhase===2?0.7:0.15));
      if(up>0.3&&up<0.7){
        for(var by=1;by<8;by++){
          var bw=1+Math.floor(by*0.4);
          rect(ux+3-Math.floor(bw/2),uy+2+by,bw,1,rgba('#79c0ff',0.04*(8-by)/8));
        }
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#f0a500',0.4));
    rect(0,H-2,W,1,rgba('#f0a500',0.1));
  };
});
