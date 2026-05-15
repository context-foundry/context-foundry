// Scene: Floating Point Lagoon
// Jokulsarlon Glacier Lagoon, Iceland
window.CF.register("Floating Point Lagoon", "Jokulsarlon Glacier Lagoon, Iceland", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Variables for dynamic elements
  var icebergs=[], iceChunks=[], shoreParticles=[];

  // Initialize icebergs
  var icebergCount=5;
  for(var i=0;i<icebergCount;i++){
    icebergs.push({
      x: Math.random() * (W - 100),
      y: Math.random() * 150 + 60,
      width: Math.random() * 40 + 40,
      height: Math.random() * 20 + 20,
      drift: (Math.random() - 0.5) * 0.2
    });
  }

  // Initialize ice chunks
  var chunkCount=10;
  for(var i=0;i<chunkCount;i++){
    iceChunks.push({
      x: Math.random() * (W - 10),
      y: Math.random() * 200 + 50,
      size: Math.random() * 5 + 5,
      life: Math.floor(Math.random() * 50) + 20,
      drift: (Math.random() - 0.5) * 0.1
    });
  }

  // Initialize shore particles
  for(var i=0; i<100; i++){
    shoreParticles.push({
      x: Math.random() * W,
      y: Math.random() * 260,
      alpha: Math.random() * 0.5 + 0.2,
      life: Math.floor(Math.random() * 30) + 10
    });
  }

  return function(t){
    // Background gradient to represent sky and water
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#adcbe3', '#6c757d', p); // Gradient from sky to deep water
      rect(0, y, W, 2, col);
    }

    // Draw Icebergs
    for(var iceberg of icebergs){
      iceberg.y += iceberg.drift; // Drift
      if (iceberg.y > H) iceberg.y = -50; // Looping effect
      rect(iceberg.x, iceberg.y, iceberg.width, iceberg.height, rgba('#caf0f8', 0.9));
      rect(iceberg.x + 5, iceberg.y + 5, iceberg.width - 10, iceberg.height - 10, rgba('#e9ecef', 0.6));
    }

    // Draw Ice Chunks
    for(var chunk of iceChunks){
      chunk.x += chunk.drift; // Drift
      if (chunk.x > W) chunk.x = -10; // Looping effect
      px(chunk.x, chunk.y, rgba('#48cae4', 0.8));
      if (chunk.life-- <= 0) {
        chunk.x = Math.random() * (W - 10);
        chunk.y = Math.random() * 80 + 180; // Resetting at the bottom
        chunk.size = Math.random() * 5 + 5;
        chunk.life = Math.floor(Math.random() * 50) + 20;
      }
      circle(chunk.x, chunk.y, chunk.size, rgba('#e9ecef', 0.5));
    }

    // Draw Black Sand Shore
    rect(0, H - 20, W, 20, '#212529');

    // Shore particles for texture in the sand
    for(var particle of shoreParticles){
      px(particle.x, particle.y, rgba('#adb5bd', particle.alpha));
      particle.y += 0.5; // Falling effect
      if (particle.y > H) {
        particle.y = Math.random() * 10; // Reset
        particle.x = Math.random() * W; // New position
      }
    }

    // Bottom glow line for consistency
    rect(0, H-1, W, 1, rgba('#48cae4', 0.3));
    rect(0, H-2, W, 1, rgba('#48cae4', 0.1));
  };
});
