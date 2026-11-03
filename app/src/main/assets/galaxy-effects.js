(() => {
  'use strict';

  const canvas = document.getElementById('cosmicCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d', { alpha: true });
  if (!ctx) return;

  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let width = 0;
  let height = 0;
  let scale = 1;
  let stars = [];
  let asteroids = [];
  let rafId = 0;
  let lastFrame = 0;
  let elapsed = 0;

  const random = (min, max) => min + Math.random() * (max - min);

  function makeAsteroid(startAtTop) {
    const radius = random(7, 16);
    const vertices = Math.floor(random(7, 11));
    const points = [];
    for (let i = 0; i < vertices; i += 1) {
      const angle = (Math.PI * 2 * i) / vertices;
      points.push({ angle, radius: radius * random(0.72, 1.18) });
    }
    const craters = [];
    for (let i = 0; i < 2; i += 1) {
      craters.push({
        angle: random(0, Math.PI * 2),
        distance: random(0.15, 0.52) * radius,
        size: random(0.65, 1.7) * Math.max(0.55, radius / 8)
      });
    }
    return {
      x: random(0, Math.max(1, width)),
      y: startAtTop ? random(-height * 0.25, height * 0.45) : random(-height * 0.35, -12),
      radius,
      points,
      craters,
      drift: random(-9, 23),
      speed: random(62, 118),
      angle: random(0, Math.PI * 2),
      spin: random(-0.35, 0.35),
      trail: random(45, 105),
      tint: Math.random() < 0.5 ? '120,188,255' : '193,157,255',
      glow: random(0.48, 0.82)
    };
  }

  function resize() {
    width = window.innerWidth || document.documentElement.clientWidth || 360;
    height = window.innerHeight || document.documentElement.clientHeight || 640;
    scale = Math.min(window.devicePixelRatio || 1, 1.35);
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    ctx.setTransform(scale, 0, 0, scale, 0, 0);

    const starCount = Math.max(48, Math.min(145, Math.floor((width * height) / 7400)));
    stars = Array.from({ length: starCount }, () => ({
      x: random(0, width),
      y: random(0, height),
      radius: random(0.35, 1.3),
      alpha: random(0.2, 0.73),
      phase: random(0, Math.PI * 2),
      twinkle: random(0.55, 1.8),
      drift: random(0.8, 3.5)
    }));
    const count = Math.max(4, Math.min(6, Math.round(width / 150)));
    asteroids = Array.from({ length: count }, () => makeAsteroid(true));
    paint(0, true);
  }

  function drawAsteroid(rock) {
    ctx.save();
    ctx.translate(rock.x, rock.y);
    ctx.rotate(rock.angle);

    const tail = ctx.createLinearGradient(0, -rock.trail, 0, rock.radius * 0.2);
    tail.addColorStop(0, `rgba(${rock.tint},0)`);
    tail.addColorStop(0.65, `rgba(${rock.tint},${rock.glow * 0.16})`);
    tail.addColorStop(1, `rgba(225,239,255,${rock.glow * 0.52})`);
    ctx.strokeStyle = tail;
    ctx.lineWidth = Math.max(1.3, rock.radius * 0.4);
    ctx.beginPath();
    ctx.moveTo(0, -rock.trail);
    ctx.lineTo(0, -rock.radius * 0.45);
    ctx.stroke();

    const body = ctx.createRadialGradient(-rock.radius * 0.32, -rock.radius * 0.35, 0.3, 0, 0, rock.radius * 1.25);
    body.addColorStop(0, '#eef5ff');
    body.addColorStop(0.33, '#9aabc9');
    body.addColorStop(0.78, '#586789');
    body.addColorStop(1, '#202a42');
    ctx.shadowColor = `rgba(${rock.tint},${rock.glow})`;
    ctx.shadowBlur = rock.radius * 1.5;
    ctx.fillStyle = body;
    ctx.strokeStyle = `rgba(205,226,255,${rock.glow * 0.43})`;
    ctx.lineWidth = 0.65;
    ctx.beginPath();
    rock.points.forEach((point, index) => {
      const x = Math.cos(point.angle) * point.radius;
      const y = Math.sin(point.angle) * point.radius;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.strokeStyle = 'rgba(21,31,52,.7)';
    rock.craters.forEach((crater) => {
      const x = Math.cos(crater.angle) * crater.distance;
      const y = Math.sin(crater.angle) * crater.distance;
      ctx.beginPath();
      ctx.arc(x, y, crater.size, 0, Math.PI * 2);
      ctx.stroke();
    });
    ctx.restore();
  }

  function paint(deltaSeconds, staticOnly) {
    ctx.clearRect(0, 0, width, height);
    for (const star of stars) {
      if (!staticOnly) star.y += star.drift * deltaSeconds;
      if (star.y > height + 2) {
        star.y = -2;
        star.x = random(0, width);
      }
      const flicker = staticOnly ? 0.78 : 0.58 + Math.sin(elapsed * star.twinkle + star.phase) * 0.24;
      ctx.fillStyle = `rgba(191,219,255,${Math.max(0.08, star.alpha * flicker)})`;
      ctx.beginPath();
      ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
      ctx.fill();
    }
    if (!staticOnly) {
      for (const rock of asteroids) {
        rock.y += rock.speed * deltaSeconds;
        rock.x += rock.drift * deltaSeconds;
        rock.angle += rock.spin * deltaSeconds;
        if (rock.y - rock.trail > height + 18 || rock.x < -45 || rock.x > width + 45) {
          Object.assign(rock, makeAsteroid(false));
        }
        drawAsteroid(rock);
      }
    }
  }

  function frame(timestamp) {
    rafId = 0;
    if (document.visibilityState === 'hidden') return;
    if (timestamp - lastFrame < 30) {
      rafId = window.requestAnimationFrame(frame);
      return;
    }
    const delta = Math.min((timestamp - (lastFrame || timestamp)) / 1000, 0.05);
    lastFrame = timestamp;
    elapsed += delta;
    paint(delta, false);
    rafId = window.requestAnimationFrame(frame);
  }

  function start() {
    if (reducedMotion) {
      paint(0, true);
      return;
    }
    if (!rafId && document.visibilityState !== 'hidden') rafId = window.requestAnimationFrame(frame);
  }

  window.addEventListener('resize', resize, { passive: true });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      if (rafId) window.cancelAnimationFrame(rafId);
      rafId = 0;
    } else {
      lastFrame = 0;
      start();
    }
  });
  resize();
  start();
})();
