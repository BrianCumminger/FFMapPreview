class MapPreviewApp {
    constructor() {
        this.canvas = document.getElementById('map-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.wrapper = document.getElementById('canvas-wrapper');
        
        this.mapData = null;
        this.tiles = [];
        this.sprites = {};
        this.labelPositions = {};
        this.drawnTextRects = {};
        this.currentFilename = 'map-preview';
        
        // View Transformation State
        this.view = { x: 0, y: 0, k: 1 };
        this.draggingLabel = null;
        this.draggingMap = false;
        this.lastMouse = { x: 0, y: 0 };
        this.dragOffset = { x: 0, y: 0 };
        this.oasisCoord = null;

        this.textMapping = {
            "BahamutCave1": "Bahamut",
            "Cardia1": "Cardia",
            "Cardia2": "Cardia",
            "Cardia4": "Cardia",
            "Cardia5": "Cardia",
            "Cardia6": "Cardia",
            "CastleOrdeals1": "Ordeals",
            "Coneria": "Coneria",
            "ConeriaCastle1": "Coneria Castle",
            "CrescentLake": "Crescent Lake",
            "DwarfCave": "Dwarf Cave",
            "EarthCave1": "Earth Cave",
            "Elfland": "Elfland",
            "ElflandCastle": "Elfland Castle",
            "Gaia": "Gaia",
            "GurguVolcano1": "Volcano",
            "IceCave1": "Ice Cave",
            "Lefein": "Lefein",
            "MarshCave1": "Marsh Cave",
            "MatoyasCave": "Matoya",
            "Melmond": "Melmond",
            "MirageTower1": "Mirage",
            "NorthwestCastle": "Northwest Castle",
            "Onrac": "Onrac",
            "Pravoka": "Pravoka",
            "SardasCave": "Sarda",
            "TempleOfFiends1": "ToF",
            "TitansTunnelEast": "Titans East",
            "TitansTunnelWest": "Titans West",
            "Waterfall": "Waterfall",
            "BridgeLocation": "Bridge",
            "CanalLocation": "Canal"
        };

        this.initEventListeners();
        this.loadAssets();
    }

    async loadAssets() {
        const loadImg = (src) => new Promise((resolve) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.src = src;
        });

        const tileset = await loadImg(ASSETS.maptiles);
        this.sprites.start = await loadImg(ASSETS.start);
        this.sprites.airship = await loadImg(ASSETS.airship);

        // Extract 16x16 tiles
        const cols = Math.floor(tileset.width / 16);
        const rows = Math.floor(tileset.height / 16);
        for (let y = 0; y < rows; y++) {
            for (let x = 0; x < cols; x++) {
                const offscreen = document.createElement('canvas');
                offscreen.width = 16;
                offscreen.height = 16;
                const oCtx = offscreen.getContext('2d');
                oCtx.drawImage(tileset, x * 16, y * 16, 16, 16, 0, 0, 16, 16);
                this.tiles.push(offscreen);
            }
        }
        console.log(`Loaded ${this.tiles.length} tiles.`);
    }

    initEventListeners() {
        document.getElementById('json-upload').addEventListener('change', (e) => this.handleFileUpload(e.target.files[0]));
        
        const wrapper = document.getElementById('canvas-wrapper');
        wrapper.addEventListener('dragover', (e) => { e.preventDefault(); wrapper.classList.add('dragover'); });
        wrapper.addEventListener('dragleave', () => wrapper.classList.remove('dragover'));
        wrapper.addEventListener('drop', (e) => {
            e.preventDefault();
            wrapper.classList.remove('dragover');
            this.handleFileUpload(e.dataTransfer.files[0]);
        });

        // UI Controls
        const controls = ['font-family', 'font-size', 'outline-size', 'line-width', 'text-color', 'outline-color'];
        controls.forEach(id => {
            document.getElementById(id).addEventListener('input', () => {
                if (id === 'font-size') document.getElementById('font-size-val').textContent = document.getElementById(id).value;
                this.refreshImage();
            });
        });

        document.getElementById('save-btn').addEventListener('click', () => this.saveImage());
        document.getElementById('reset-btn').addEventListener('click', () => {
            this.labelPositions = {};
            this.refreshImage();
        });

        const fitBtn = document.createElement('button');
        fitBtn.id = 'fit-btn';
        fitBtn.className = 'secondary-btn';
        fitBtn.textContent = 'Fit to Screen';
        fitBtn.addEventListener('click', () => this.autoFit());
        document.querySelector('.actions').appendChild(fitBtn);

        // Mouse interaction for dragging and zooming
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e), { passive: false });
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        window.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        window.addEventListener('mouseup', () => {
            this.draggingLabel = null;
            this.draggingMap = false;
        });

        // Resize handler
        window.addEventListener('resize', () => {
            this.resizeCanvas();
            this.refreshImage();
        });
        this.resizeCanvas();
    }

    resizeCanvas() {
        const rect = this.wrapper.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }

    autoFit() {
        if (!this.offscreenCanvas) return;
        const padding = 40;
        const availableW = this.canvas.width - padding * 2;
        const availableH = this.canvas.height - padding * 2;
        const mapW = this.offscreenCanvas.width;
        const mapH = this.offscreenCanvas.height;

        const scale = Math.min(availableW / mapW, availableH / mapH);
        this.view.k = scale;
        this.view.x = (this.canvas.width - mapW * scale) / 2;
        this.view.y = (this.canvas.height - mapH * scale) / 2;
        this.refreshImage();
    }

    handleWheel(e) {
        e.preventDefault();
        const mouse = this.getRawMousePos(e);
        const zoomSpeed = 0.001;
        const delta = -e.deltaY;
        const factor = Math.pow(1.1, delta / 100);
        
        const newK = Math.min(Math.max(this.view.k * factor, 0.01), 20);
        
        // Zoom centered at mouse position
        // World position before zoom
        const wx = (mouse.x - this.view.x) / this.view.k;
        const wy = (mouse.y - this.view.y) / this.view.k;

        this.view.k = newK;
        
        // Update offset to keep world position under mouse
        this.view.x = mouse.x - wx * this.view.k;
        this.view.y = mouse.y - wy * this.view.k;

        this.refreshImage();
    }

    async showConfirm(title, message) {
        return new Promise((resolve) => {
            const overlay = document.getElementById('custom-modal');
            const titleEl = document.getElementById('modal-title');
            const messageEl = document.getElementById('modal-message');
            const yesBtn = document.getElementById('modal-yes');
            const noBtn = document.getElementById('modal-no');

            titleEl.textContent = title;
            messageEl.textContent = message;
            overlay.classList.add('active');

            const cleanup = (value) => {
                overlay.classList.remove('active');
                yesBtn.removeEventListener('click', onYes);
                noBtn.removeEventListener('click', onNo);
                resolve(value);
            };

            const onYes = () => cleanup(true);
            const onNo = () => cleanup(false);

            yesBtn.addEventListener('click', onYes);
            noBtn.addEventListener('click', onNo);
        });
    }

    handleFileUpload(file) {
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const newMapData = JSON.parse(e.target.result);
                
                // Update filename display
                const filenameDisplay = document.getElementById('current-filename');
                filenameDisplay.textContent = file.name;
                filenameDisplay.title = file.name;
                this.currentFilename = file.name.replace(/\.[^/.]+$/, "");

                let preserve = false;
                if (this.mapData && Object.keys(this.labelPositions).length > 0) {
                    preserve = await this.showConfirm(
                        "Preserve Labels?", 
                        "Would you like to keep your manual label placements for locations that haven't moved?"
                    );
                }

                if (preserve) {
                    const oldCoords = this.getCoordsFromData(this.mapData);
                    const newCoords = this.getCoordsFromData(newMapData);
                    const newLabelPositions = {};

                    for (const name in this.labelPositions) {
                        if (oldCoords[name] && newCoords[name]) {
                            const oldPos = oldCoords[name];
                            const newPos = newCoords[name];
                            if (oldPos.X === newPos.X && oldPos.Y === newPos.Y) {
                                newLabelPositions[name] = this.labelPositions[name];
                            }
                        }
                    }
                    this.labelPositions = newLabelPositions;
                } else {
                    this.labelPositions = {};
                }

                this.mapData = newMapData;
                this.generateBaseMap();
            } catch (err) {
                alert("Error parsing JSON file: " + err.message);
            }
        };
        reader.readAsText(file);
    }

    getCoordsFromData(data) {
        const coords = {};
        if (data.OverworldCoordinates) Object.assign(coords, data.OverworldCoordinates);
        if (data.BridgeLocation) coords.BridgeLocation = data.BridgeLocation;
        if (data.CanalLocation) coords.CanalLocation = data.CanalLocation;
        if (this.oasisCoord) coords.Oasis = this.oasisCoord;
        return coords;
    }

    generateBaseMap() {
        if (!this.mapData || !this.mapData.DecompressedMapRows) return;
        
        const rows = this.mapData.DecompressedMapRows.map(row => {
            // Base64 to Uint8Array
            const binaryString = atob(row);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i);
            return bytes;
        });

        const h = rows.length;
        const w = rows[0].length;
        
        this.offscreenCanvas = document.createElement('canvas');
        this.offscreenCanvas.width = w * 16;
        this.offscreenCanvas.height = h * 16;
        const oCtx = this.offscreenCanvas.getContext('2d');

        this.oasisCoord = null;
        rows.forEach((row, y) => {
            row.forEach((tileIdx, x) => {
                if (this.tiles[tileIdx]) {
                    oCtx.drawImage(this.tiles[tileIdx], x * 16, y * 16);
                    if (!this.oasisCoord && tileIdx === 0x36) this.oasisCoord = { X: x, Y: y };
                }
            });
        });

        this.autoFit();
    }

    refreshImage() {
        if (!this.offscreenCanvas) return;

        // Clear and draw base map
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.ctx.save();
        this.ctx.translate(this.view.x, this.view.y);
        this.ctx.scale(this.view.k, this.view.k);

        this.ctx.drawImage(this.offscreenCanvas, 0, 0);

        const fontSize = parseInt(document.getElementById('font-size').value);
        const fontFamily = document.getElementById('font-family').value;
        const outlineSize = parseInt(document.getElementById('outline-size').value);
        const lineWidth = parseInt(document.getElementById('line-width').value);
        const textColor = document.getElementById('text-color').value;
        const outlineColor = document.getElementById('outline-color').value;

        this.ctx.font = `${fontSize}px "${fontFamily}"`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';

        const coords = this.getCoordsFromData(this.mapData);
        const sortedKeys = Object.keys(coords).sort((a, b) => {
            const ya = coords[a].Y || 0;
            const yb = coords[b].Y || 0;
            if (ya !== yb) return ya - yb;
            return (coords[a].X || 0) - (coords[b].X || 0);
        });

        this.drawnTextRects = {};
        const drawnRects = [];

        // 1. Pre-calculate rects for PRESERVED labels so auto-layout avoids them
        sortedKeys.forEach(name => {
            if (this.labelPositions[name]) {
                const displayName = this.textMapping[name] || name;
                const metrics = this.ctx.measureText(displayName);
                const textW = Math.abs(metrics.actualBoundingBoxLeft) + Math.abs(metrics.actualBoundingBoxRight) || (metrics.width);
                const textH = fontSize;
                const lp = this.labelPositions[name];
                
                const preservedRect = {
                    x: lp.x - textW / 2,
                    y: lp.y - textH / 2,
                    w: textW,
                    h: textH
                };
                drawnRects.push(preservedRect);
                this.drawnTextRects[name] = preservedRect;
            }
        });

        // 2. Calculate layout for NEW or RESET labels
        sortedKeys.forEach(name => {
            const pos = coords[name];
            const displayName = this.textMapping[name] || name;
            const metrics = this.ctx.measureText(displayName);
            const textW = Math.abs(metrics.actualBoundingBoxLeft) + Math.abs(metrics.actualBoundingBoxRight) || (metrics.width);
            const textH = fontSize;

            if (!this.labelPositions[name]) {
                const targetX = pos.X * 16 + 8;
                const targetY = pos.Y * 16 + 8;
                
                let offX = targetX;
                let offY = targetY + fontSize + 48; // Nudge

                let overlap = true;
                let iters = 0;
                while (overlap && iters < 100) {
                    const currentRect = {
                        x: offX - textW / 2,
                        y: offY - textH / 2,
                        w: textW,
                        h: textH
                    };

                    overlap = drawnRects.some(r => this.intersect(currentRect, r));
                    if (overlap) offY += fontSize * 0.1 + 2;
                    iters++;
                }
                this.labelPositions[name] = { x: offX, y: offY };
                
                const realRect = {
                    x: offX - textW / 2,
                    y: offY - textH / 2,
                    w: textW,
                    h: textH
                };
                drawnRects.push(realRect);
                this.drawnTextRects[name] = realRect;
            }
        });

        // 2. Draw lines
        if (lineWidth > 0) {
            this.ctx.lineJoin = 'round';
            this.ctx.lineCap = 'round';
            
            sortedKeys.forEach(name => {
                const pos = coords[name];
                const lp = this.labelPositions[name];
                const tx = pos.X * 16 + 8;
                const ty = pos.Y * 16 + 8;

                // Outline for line
                this.ctx.strokeStyle = '#000000';
                this.ctx.lineWidth = lineWidth + 8;
                this.ctx.beginPath();
                this.ctx.moveTo(tx, ty);
                this.ctx.lineTo(lp.x, lp.y);
                this.ctx.stroke();

                // Main line
                this.ctx.strokeStyle = textColor;
                this.ctx.lineWidth = lineWidth;
                this.ctx.beginPath();
                this.ctx.moveTo(tx, ty);
                this.ctx.lineTo(lp.x, lp.y);
                this.ctx.stroke();
            });
        }

        // 3. Draw text
        sortedKeys.forEach(name => {
            const displayName = this.textMapping[name] || name;
            const lp = this.labelPositions[name];
            
            this.ctx.lineWidth = outlineSize;
            this.ctx.strokeStyle = outlineColor;
            this.ctx.fillStyle = textColor;

            if (outlineSize > 0) this.ctx.strokeText(displayName, lp.x, lp.y);
            this.ctx.fillText(displayName, lp.x, lp.y);
        });

        // 4. Draw Sprite markers
        this.drawSprite('StartingLocation', this.sprites.start);
        this.drawSprite('AirShipLocation', this.sprites.airship);

        this.ctx.restore();
    }

    drawSprite(key, img) {
        if (this.mapData && this.mapData[key] && img) {
            const pos = this.mapData[key];
            const sw = img.width * 5;
            const sh = img.height * 5;
            this.ctx.imageSmoothingEnabled = false;
            this.ctx.drawImage(img, pos.X * 16 + 8 - sw / 2, pos.Y * 16 + 8 - sh / 2, sw, sh);
        }
    }

    intersect(r1, r2) {
        // Reduced collision box for better grouping (same as Python 0.8/0.6 factor)
        const p1 = { x: r1.x + r1.w * 0.1, y: r1.y + r1.h * 0.2, w: r1.w * 0.8, h: r1.h * 0.6 };
        const p2 = { x: r2.x + r2.w * 0.1, y: r2.y + r2.h * 0.2, w: r2.w * 0.8, h: r2.h * 0.6 };
        return !(p2.x > p1.x + p1.w || p2.x + p2.w < p1.x || p2.y > p1.y + p1.h || p2.y + p2.h < p1.y);
    }

    getRawMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }

    getMousePos(e) {
        const mouse = this.getRawMousePos(e);
        return {
            x: (mouse.x - this.view.x) / this.view.k,
            y: (mouse.y - this.view.y) / this.view.k
        };
    }

    handleMouseDown(e) {
        const mouse = this.getMousePos(e);
        const raw = this.getRawMousePos(e);

        if (e.button === 1 || e.button === 2 || (e.button === 0 && e.altKey)) {
            this.draggingMap = true;
            this.lastMouse = raw;
            return;
        }

        const keys = Object.keys(this.drawnTextRects).reverse();
        for (const name of keys) {
            const r = this.drawnTextRects[name];
            if (mouse.x >= r.x && mouse.x <= r.x + r.w && mouse.y >= r.y && mouse.y <= r.y + r.h) {
                this.draggingLabel = name;
                this.dragOffset = { x: this.labelPositions[name].x - mouse.x, y: this.labelPositions[name].y - mouse.y };
                break;
            }
        }
    }

    handleMouseMove(e) {
        const raw = this.getRawMousePos(e);
        const mouse = this.getMousePos(e);

        if (this.draggingMap) {
            this.view.x += raw.x - this.lastMouse.x;
            this.view.y += raw.y - this.lastMouse.y;
            this.lastMouse = raw;
            this.refreshImage();
            return;
        }

        if (!this.draggingLabel) return;
        this.labelPositions[this.draggingLabel] = {
            x: mouse.x + this.dragOffset.x,
            y: mouse.y + this.dragOffset.y
        };
        this.refreshImage();
    }

    saveImage() {
        const saveCanvas = document.createElement('canvas');
        saveCanvas.width = this.offscreenCanvas.width;
        saveCanvas.height = this.offscreenCanvas.height;
        const sCtx = saveCanvas.getContext('2d');
        
        this.drawFullResolution(sCtx);

        try {
            const imageData = sCtx.getImageData(0, 0, saveCanvas.width, saveCanvas.height);
            // UPNG.encode(data, width, height, colors)
            // colors=0 for lossless, or e.g. 256 for paletted
            const output = UPNG.encode([imageData.data.buffer], saveCanvas.width, saveCanvas.height, 0);
            
            const blob = new Blob([output], { type: 'image/png' });
            const url = URL.createObjectURL(blob);
            
            const link = document.createElement('a');
            link.download = `${this.currentFilename}.png`;
            link.href = url;
            link.click();
            
            // Cleanup
            setTimeout(() => URL.revokeObjectURL(url), 100);
        } catch (err) {
            console.error("Advanced compression failed, falling back to default:", err);
            const link = document.createElement('a');
            link.download = `${this.currentFilename}.png`;
            link.href = saveCanvas.toDataURL('image/png');
            link.click();
        }
    }

    drawFullResolution(ctx) {
        ctx.drawImage(this.offscreenCanvas, 0, 0);
        
        const fontSize = parseInt(document.getElementById('font-size').value);
        const fontFamily = document.getElementById('font-family').value;
        const outlineSize = parseInt(document.getElementById('outline-size').value);
        const lineWidth = parseInt(document.getElementById('line-width').value);
        const textColor = document.getElementById('text-color').value;
        const outlineColor = document.getElementById('outline-color').value;

        ctx.font = `${fontSize}px "${fontFamily}"`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const coords = this.getCoordsFromData(this.mapData);
        const sortedKeys = Object.keys(coords).sort((a, b) => {
            const ya = coords[a].Y || 0;
            const yb = coords[b].Y || 0;
            if (ya !== yb) return ya - yb;
            return (coords[a].X || 0) - (coords[b].X || 0);
        });

        // Lines
        if (lineWidth > 0) {
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            sortedKeys.forEach(name => {
                const pos = coords[name];
                const lp = this.labelPositions[name];
                const tx = pos.X * 16 + 8;
                const ty = pos.Y * 16 + 8;
                ctx.strokeStyle = '#000000';
                ctx.lineWidth = lineWidth + 8;
                ctx.beginPath();
                ctx.moveTo(tx, ty);
                ctx.lineTo(lp.x, lp.y);
                ctx.stroke();
                ctx.strokeStyle = textColor;
                ctx.lineWidth = lineWidth;
                ctx.beginPath();
                ctx.moveTo(tx, ty);
                ctx.lineTo(lp.x, lp.y);
                ctx.stroke();
            });
        }

        // Text
        sortedKeys.forEach(name => {
            const displayName = this.textMapping[name] || name;
            const lp = this.labelPositions[name];
            ctx.lineWidth = outlineSize;
            ctx.strokeStyle = outlineColor;
            ctx.fillStyle = textColor;
            if (outlineSize > 0) ctx.strokeText(displayName, lp.x, lp.y);
            ctx.fillText(displayName, lp.x, lp.y);
        });

        // Sprites
        this.drawSpriteToCtx('StartingLocation', this.sprites.start, ctx);
        this.drawSpriteToCtx('AirShipLocation', this.sprites.airship, ctx);
    }

    drawSpriteToCtx(key, img, ctx) {
        if (this.mapData && this.mapData[key] && img) {
            const pos = this.mapData[key];
            const sw = img.width * 5;
            const sh = img.height * 5;
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(img, pos.X * 16 + 8 - sw / 2, pos.Y * 16 + 8 - sh / 2, sw, sh);
        }
    }
}

// Start app
window.onload = () => new MapPreviewApp();
