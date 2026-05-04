import React, { useState, useEffect, useRef } from "react";
import { Rnd } from "react-rnd";

export default function MockupPositionTool() {
  const [mockup, setMockup] = useState(null);
  const [trial, setTrial] = useState(null);

  const [box, setBox] = useState({
    x: 100,
    y: 100,
    width: 250,
    height: 350,
  });

  const [scale, setScale] = useState(1);
  const imgRef = useRef(null);

  // Arrow keys
  useEffect(() => {
    const handleKey = (e) => {
      let step = e.shiftKey ? 10 : 1;

      if (e.key === "ArrowUp") setBox((b) => ({ ...b, y: b.y - step }));
      if (e.key === "ArrowDown") setBox((b) => ({ ...b, y: b.y + step }));
      if (e.key === "ArrowLeft") setBox((b) => ({ ...b, x: b.x - step }));
      if (e.key === "ArrowRight") setBox((b) => ({ ...b, x: b.x + step }));
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  // Calculate scale
  const handleImageLoad = () => {
    const img = imgRef.current;
    if (!img) return;

    const displayedWidth = img.clientWidth;
    const naturalWidth = img.naturalWidth;

    const scaleFactor = naturalWidth / displayedWidth;
    setScale(scaleFactor);
  };

  const move = (dx, dy) => {
    setBox((b) => ({ ...b, x: b.x + dx, y: b.y + dy }));
  };

  const resetBox = () => {
    setBox({ x: 100, y: 100, width: 250, height: 350 });
  };

  const realValues = {
    x: Math.round(box.x * scale),
    y: Math.round(box.y * scale),
    width: Math.round(box.width * scale),
    height: Math.round(box.height * scale),
  };

  return (
    <div className="h-screen flex bg-gray-100">

      {/* LEFT PANEL */}
      <div className="w-[320px] bg-white shadow-xl p-5 flex flex-col gap-5">

        <h2 className="text-xl font-bold">Controls</h2>

        {/* Upload */}
        <div className="space-y-3">
          <input
            type="file"
            className="w-full border p-2 rounded"
            onChange={(e) => setMockup(URL.createObjectURL(e.target.files[0]))}
          />
          <input
            type="file"
            className="w-full border p-2 rounded"
            onChange={(e) => setTrial(URL.createObjectURL(e.target.files[0]))}
          />
        </div>

        {/* Arrows */}
        <div>
          <h3 className="font-semibold mb-2">Move</h3>

          <div className="grid grid-cols-3 gap-2 w-32 mx-auto">
            <div></div>
            <button onClick={() => move(0, -1)} className="btn">↑</button>
            <div></div>

            <button onClick={() => move(-1, 0)} className="btn">←</button>
            <button onClick={() => move(0, 1)} className="btn">↓</button>
            <button onClick={() => move(1, 0)} className="btn">→</button>
          </div>

          <p className="text-xs text-gray-500 text-center mt-2">
            Shift + arrows = faster
          </p>
        </div>

        {/* Inputs */}
        <div className="space-y-2">
          {["x", "y", "width", "height"].map((key) => (
            <div key={key} className="flex gap-2 items-center">
              <span className="w-16 capitalize">{key}</span>
              <input
                type="number"
                value={box[key]}
                onChange={(e) =>
                  setBox({ ...box, [key]: parseInt(e.target.value) || 0 })
                }
                className="border p-2 rounded w-full"
              />
            </div>
          ))}
        </div>

        {/* Buttons */}
        <div className="space-y-2">
          <button
            onClick={() =>
              navigator.clipboard.writeText(JSON.stringify(realValues))
            }
            className="w-full bg-blue-500 text-white p-2 rounded"
          >
            Copy REAL Values
          </button>

          <button
            onClick={resetBox}
            className="w-full bg-gray-200 p-2 rounded"
          >
            Reset
          </button>
        </div>

        {/* Output */}
        <div className="text-xs bg-gray-100 p-3 rounded overflow-auto">
          <p className="font-semibold">Displayed:</p>
          {JSON.stringify(box, null, 2)}

          <p className="font-semibold mt-2">Real (for Python):</p>
          {JSON.stringify(realValues, null, 2)}
        </div>
      </div>

      {/* RIGHT CANVAS */}
      <div className="flex-1 flex items-center justify-center p-6">

        <div className="w-[900px] h-[650px] bg-white shadow-xl rounded-lg flex items-center justify-center relative overflow-hidden">

          {mockup && (
            <img
              ref={imgRef}
              src={mockup}
              alt="mockup"
              onLoad={handleImageLoad}
              className="w-full h-full object-contain pointer-events-none"
            />
          )}

          {trial && (
            <Rnd
              size={{ width: box.width, height: box.height }}
              position={{ x: box.x, y: box.y }}
              bounds="parent"
              onDragStop={(e, d) => {
                setBox((prev) => ({ ...prev, x: d.x, y: d.y }));
              }}
              onResizeStop={(e, dir, ref, delta, pos) => {
                setBox({
                  x: pos.x,
                  y: pos.y,
                  width: parseInt(ref.style.width),
                  height: parseInt(ref.style.height),
                });
              }}
            >
              <div className="w-full h-full border-2 border-dashed border-blue-500 bg-white rounded overflow-hidden">
                <img
                  src={trial}
                  alt="trial"
                  className="w-full h-full object-contain pointer-events-none"
                />
              </div>
            </Rnd>
          )}

        </div>
      </div>

      <style>
        {`
          .btn {
            background: #e5e7eb;
            padding: 8px;
            border-radius: 6px;
            font-weight: bold;
          }
          .btn:hover {
            background: #d1d5db;
          }
        `}
      </style>
    </div>
  );
}