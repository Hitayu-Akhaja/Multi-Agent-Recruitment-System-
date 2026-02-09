import { useEffect, useRef } from "react";

export default function PixelTrailBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;

    const cellSize = 28;
    const fadeStep = 0.03;
    const glowColor = "79, 70, 229";

    let width = 0;
    let height = 0;
    let cols = 0;
    let rows = 0;
    let animationId = 0;
    const pixels = [];
    const mouse = { x: -1000, y: -1000 };
    let contentLayer = null;

    const buildGrid = () => {
      const dpr = window.devicePixelRatio || 1;
      width = window.innerWidth;
      height = window.innerHeight;

      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      cols = Math.ceil(width / cellSize);
      rows = Math.ceil(height / cellSize);

      pixels.length = 0;
      for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
          pixels.push({
            x: col * cellSize,
            y: row * cellSize,
            opacity: 0
          });
        }
      }
    };

    const handlePointerMove = (event) => {
      if (contentLayer && contentLayer.contains(event.target)) {
        mouse.x = -1000;
        mouse.y = -1000;
        return;
      }
      mouse.x = event.clientX;
      mouse.y = event.clientY;
    };

    const handlePointerLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };

    const animate = () => {
      ctx.clearRect(0, 0, width, height);

      pixels.forEach((pixel) => {
        if (
          mouse.x > pixel.x &&
          mouse.x < pixel.x + cellSize &&
          mouse.y > pixel.y &&
          mouse.y < pixel.y + cellSize
        ) {
          pixel.opacity = 1;
        }

        if (pixel.opacity > 0) {
          pixel.opacity = Math.max(0, pixel.opacity - fadeStep);
          ctx.fillStyle = `rgba(${glowColor}, ${pixel.opacity})`;
          ctx.fillRect(
            pixel.x + 1,
            pixel.y + 1,
            cellSize - 2,
            cellSize - 2
          );
        }
      });

      animationId = window.requestAnimationFrame(animate);
    };

    contentLayer = document.querySelector(".content-layer");
    buildGrid();
    animate();

    window.addEventListener("resize", buildGrid);
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerleave", handlePointerLeave);

    return () => {
      window.removeEventListener("resize", buildGrid);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerleave", handlePointerLeave);
      window.cancelAnimationFrame(animationId);
    };
  }, []);

  return <canvas className="pixel-canvas" ref={canvasRef} aria-hidden="true" />;
}
