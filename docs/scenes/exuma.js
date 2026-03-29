// Scene: Where Pigs Fly (and Swim)
// Big Major Cay, Exuma, Bahamas
window.CF.register("Where Pigs Fly (and Swim)", "Big Major Cay, Exuma, Bahamas", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Particle systems
  var bubbles=[];
  for(var i=0;i<25;i++){
    bubbles.push({x:150+Math.random()*280,y:140+Math.random()*120,vy:-0.2-Math.random()*0.5,vx:(Math.random()-0.5)*0.2,life:60+Math.random()*120,maxLife:180,r:1+Math.floor(Math.random()*2)});
  }
  var fish=[];
  for(var i=0;i<5;i++){
    fish.push({
      x:120+Math.random()*300,y:140+Math.random()*100,
      baseX:120+Math.random()*300,baseY:140+Math.random()*100,
      col:['#FFD54F','#42A5F5','#FF7043','#66BB6A','#CE93D8'][i],
      phase:Math.random()*Math.PI*2,speed:0.3+Math.random()*0.4,range:20+Math.random()*30,
      dir:Math.random()>0.5?1:-1,size:4+Math.floor(Math.random()*3)
    });
  }

  return function(t){
    // === SKY (y: 0-75) ===
    for(var y=0;y<76;y++){
      var p=y/75;
      rect(0,y,W,1,lerp('#E0F7FA','#4FC3F7',p));
    }

    // === SUN (upper right) ===
    var sunX=W-90, sunY=30;
    for(var dy=-18;dy<=18;dy++){
      for(var dx=-18;dx<=18;dx++){
        var d=Math.sqrt(dx*dx+dy*dy);
        if(d>8&&d<18) px(sunX+dx,sunY+dy,rgba('#FFF9C4',0.02*(18-d)/10));
      }
    }
    circle(sunX,sunY,8,rgba('#FFF176',0.9));
    circle(sunX,sunY,6,'#FFEE58');
    circle(sunX,sunY,4,'#FFF9C4');

    // === CLOUDS ===
    function drawCloud(cx,cy,w){
      var drift=(t*0.3+cx)%((W+120))-60;
      for(var i=0;i<w;i++){
        var ch=3+Math.sin(i*0.5)*2;
        for(var dy=-ch;dy<=ch;dy++){
          var a=0.6-Math.abs(dy)*0.1;
          if(a>0) px(drift+i,cy+dy,rgba('#ffffff',a));
        }
      }
    }
    drawCloud(50,18,30);
    drawCloud(200,12,24);
    drawCloud(380,22,20);
    drawCloud(140,28,16);

    // === SEAGULLS ===
    function drawGull(bx,by,phase){
      var gx=(bx+t*12)%(W+40)-20;
      var gy=by+Math.sin(t*1.5+phase)*3;
      var wingUp=Math.sin(t*3+phase)*2;
      px(gx-3,gy-wingUp,'#546E7A');
      px(gx-2,gy-wingUp*0.6,'#546E7A');
      px(gx-1,gy,'#37474F');
      px(gx,gy,'#37474F');
      px(gx+1,gy,'#37474F');
      px(gx+2,gy-wingUp*0.6,'#546E7A');
      px(gx+3,gy-wingUp,'#546E7A');
    }
    drawGull(60,35,0);
    drawGull(180,40,1.5);
    drawGull(320,32,3.0);

    // === BEACH (left 35%) ===
    var beachEdge=Math.floor(W*0.35);
    for(var y=60;y<H;y++){
      var beachW=beachEdge-Math.floor((y-60)*0.8);
      if(beachW>0){
        for(var x=0;x<beachW;x++){
          var sandP=y/H;
          var col=sandP<0.5?'#FFF8E1':'#FFECB3';
          px(x,y,col);
        }
        if(y>90&&y<120){
          var foamX=beachW+Math.sin(y*0.3+t*2)*2;
          px(foamX,y,rgba('#ffffff',0.5+osc(t,2,y*0.1)*0.3));
          px(foamX+1,y,rgba('#ffffff',0.3));
        }
      }
    }
    var sandR=srand(777);
    for(var i=0;i<120;i++){
      var sx=Math.floor(sandR()*beachEdge*0.8);
      var sy=65+Math.floor(sandR()*(H-65));
      if(sx<beachEdge-Math.floor((sy-60)*0.8)){
        px(sx,sy,rgba('#FFCC80',0.3+sandR()*0.3));
      }
    }

    // === PALM TREES ===
    function drawPalm(bx,by,lean){
      for(var i=0;i<35;i++){
        var tx=bx+Math.sin(i*0.06+lean)*i*0.15;
        var ty=by-i;
        px(tx,ty,'#5D4037');
        px(tx+1,ty,'#6D4C41');
        if(i%4===0) px(tx,ty,'#4E342E');
      }
      var topX=bx+Math.sin(35*0.06+lean)*35*0.15;
      var topY=by-35;
      var frondAngles=[-2.2,-1.5,-0.8,-0.2,0.4,1.0,1.6,2.2];
      for(var fa of frondAngles){
        for(var fl=0;fl<16;fl++){
          var fx=topX+Math.cos(fa)*fl;
          var fy=topY+Math.sin(fa)*fl*0.5+fl*fl*0.02;
          var sway=Math.sin(t*0.8+fa)*1.5*fl/16;
          var green=fl<8?'#2E7D32':'#43A047';
          px(fx+sway,fy,green);
          if(fl>3&&fl%2===0){
            px(fx+sway-1,fy+1,'#66BB6A');
            px(fx+sway+1,fy+1,'#66BB6A');
          }
        }
      }
      px(topX-1,topY+2,'#5D4037');
      px(topX+1,topY+2,'#795548');
    }
    drawPalm(40,H-50,0.3);
    drawPalm(95,H-55,-0.2);

    // === WATER SURFACE (y: 75-110) ===
    for(var y=76;y<110;y++){
      for(var x=0;x<W;x++){
        var beachW2=beachEdge-Math.floor((y-60)*0.8);
        if(x<beachW2) continue;
        var wave=Math.sin(x*0.08+t*2+y*0.3)*0.5;
        var p=(y-76)/34;
        var col=p<0.5?lerp('#4DD0E1','#00BCD4',p*2+wave*0.1):lerp('#00BCD4','#00897B',(p-0.5)*2);
        px(x,y,col);
      }
    }

    // Surface sparkles
    var sparkR=srand(333);
    for(var i=0;i<40;i++){
      var sx=beachEdge+Math.floor(sparkR()*(W-beachEdge));
      var sy=78+Math.floor(sparkR()*28);
      var a=osc(t,0.5+sparkR()*2,i*2.1)*0.6;
      if(a>0.3) px(sx,sy,rgba('#ffffff',a));
    }

    // Waterline foam
    for(var x=beachEdge-20;x<W;x++){
      var wy=95+Math.sin(x*0.06+t*1.5)*2;
      if(Math.sin(x*0.3+t*4)>0.5) px(x,wy,rgba('#ffffff',0.4));
    }

    // === SWIMMING PIGS ===
    function drawPig(pigX,pigY,phase){
      var bob=Math.sin(t*1.2+phase)*1.5;
      var headY=pigY+bob;
      for(var w=1;w<8;w++){
        px(pigX-5-w,headY+1,rgba('#ffffff',0.15-w*0.015));
        px(pigX-5-w,headY+2,rgba('#B2EBF2',0.1-w*0.01));
      }
      for(var dy=2;dy<8;dy++){
        for(var dx=-5;dx<=5;dx++){
          if(dx*dx+dy*dy<40){
            px(pigX+dx,headY+dy,rgba('#FFAB91',0.15-dy*0.015));
          }
        }
      }
      circle(pigX,headY,4,'#FFAB91');
      circle(pigX,headY,3,'#FF8A65');
      px(pigX-3,headY-3,'#FFAB91');
      px(pigX-4,headY-4,'#FF8A65');
      px(pigX+3,headY-3,'#FFAB91');
      px(pigX+4,headY-4,'#FF8A65');
      px(pigX-2,headY-1,'#3E2723');
      px(pigX+2,headY-1,'#3E2723');
      px(pigX,headY+1,'#FFCCBC');
      px(pigX-1,headY+1,'#FFCCBC');
      px(pigX+1,headY+1,'#FFCCBC');
      px(pigX-1,headY+2,'#D7CCC8');
      px(pigX+1,headY+2,'#D7CCC8');
    }
    drawPig(200,90,0);
    drawPig(310,88,2.5);

    // === UNDERWATER (y: 110-H) ===
    for(var y=110;y<H;y++){
      var p=(y-110)/(H-110);
      for(var x=0;x<W;x++){
        var beachW3=beachEdge-Math.floor((y-60)*0.8);
        if(x<beachW3) continue;
        var col=lerp('#00897B','#004D40',p);
        px(x,y,col);
      }
    }

    // Light rays underwater
    for(var ray=0;ray<4;ray++){
      var rayX=120+ray*90;
      var sway=Math.sin(t*0.4+ray*1.7)*8;
      for(var y=110;y<H-30;y++){
        var ry=y-110;
        var spread=ry*0.15;
        var cx=rayX+sway+ry*0.3;
        for(var dx=-spread;dx<=spread;dx++){
          var a=0.03*(1-Math.abs(dx)/Math.max(spread,1))*(1-ry/(H-140));
          if(a>0.005) px(cx+dx,y,rgba('#ffffff',a));
        }
      }
    }

    // === CORAL REEF ===
    function drawBranchCoral(bx,by,h,col1,col2){
      for(var i=0;i<h;i++){
        px(bx,by-i,col1);
        if(i>4&&i%3===0){
          for(var b=1;b<5;b++){
            px(bx-b,by-i-b,col2);
            px(bx+b,by-i-b,col2);
          }
        }
      }
    }
    drawBranchCoral(180,H-5,22,'#EF5350','#E57373');
    drawBranchCoral(220,H-3,18,'#FF7043','#FF8A65');
    drawBranchCoral(350,H-4,25,'#EF5350','#EF9A9A');
    drawBranchCoral(400,H-6,15,'#FF7043','#FFAB91');

    function drawBrainCoral(cx,cy,r){
      for(var dy=-r;dy<=r;dy++){
        for(var dx=-r;dx<=r;dx++){
          if(dx*dx+dy*dy<=r*r){
            var ridge=Math.sin(dx*1.2+dy*0.8)*0.3>0;
            px(cx+dx,cy+dy,ridge?'#F48FB1':'#EC407A');
          }
        }
      }
    }
    drawBrainCoral(260,H-8,6);
    drawBrainCoral(310,H-6,4);

    function drawFanCoral(fx,fy,h){
      for(var i=0;i<h;i++){
        var spread=Math.floor(i*0.6);
        for(var dx=-spread;dx<=spread;dx++){
          if((dx+i)%2===0) px(fx+dx,fy-i,'#AB47BC');
          else px(fx+dx,fy-i,rgba('#CE93D8',0.6));
        }
      }
    }
    drawFanCoral(290,H-4,16);
    drawFanCoral(370,H-5,12);

    function drawAnemone(ax,ay){
      for(var t2=0;t2<7;t2++){
        var angle=-1.5+t2*0.5;
        for(var l=0;l<8;l++){
          var sway2=Math.sin(t*2+t2+l*0.3)*1.5;
          var tx=ax+Math.cos(angle)*l+sway2;
          var ty=ay-l-Math.sin(angle)*l*0.3;
          px(tx,ty,l<5?'#66BB6A':'#A5D6A7');
        }
      }
      rect(ax-2,ay,5,3,'#4CAF50');
    }
    drawAnemone(240,H-4);
    drawAnemone(330,H-5);

    // === TROPICAL FISH ===
    for(var f of fish){
      f.x=f.baseX+Math.sin(t*f.speed+f.phase)*f.range;
      f.y=f.baseY+Math.cos(t*f.speed*0.7+f.phase)*8;
      var dir=Math.cos(t*f.speed+f.phase)>0?1:-1;
      for(var dx=-f.size/2;dx<=f.size/2;dx++){
        var bh=Math.max(1,f.size/2-Math.abs(dx)*0.8);
        for(var dy=-bh;dy<=bh;dy++){
          px(f.x+dx,f.y+dy,f.col);
        }
      }
      var tailFlick=Math.sin(t*6+f.phase)*1.5;
      px(f.x-dir*(f.size/2+1),f.y+tailFlick,f.col);
      px(f.x-dir*(f.size/2+2),f.y+tailFlick-1,rgba(f.col,0.6));
      px(f.x-dir*(f.size/2+2),f.y+tailFlick+1,rgba(f.col,0.6));
      px(f.x+dir*Math.floor(f.size/3),f.y-1,'#1a1a1a');
    }

    // === SAND FLOOR ===
    var floorR=srand(555);
    for(var x=beachEdge-30;x<W;x+=2){
      var sandH=3+Math.sin(x*0.05)*2;
      for(var dy=0;dy<sandH;dy++){
        px(x,H-dy,rgba('#FFCC80',0.3+floorR()*0.2));
        px(x+1,H-dy,rgba('#FFB74D',0.2+floorR()*0.2));
      }
    }

    // === BUBBLES ===
    for(var b of bubbles){
      b.y+=b.vy;
      b.x+=b.vx+Math.sin(t*2+b.x*0.1)*0.2;
      b.life--;
      if(b.life<=0||b.y<105){
        b.x=150+Math.random()*280;
        b.y=H-10-Math.random()*30;
        b.life=60+Math.random()*120;
        b.maxLife=b.life;
      }
      var a=(b.life/b.maxLife)*0.35;
      circle(b.x,b.y,b.r,rgba('#B2EBF2',a));
      px(b.x-1,b.y-1,rgba('#ffffff',a*0.6));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#00BCD4',0.3));
    rect(0,H-2,W,1,rgba('#00897B',0.15));
  };
});
