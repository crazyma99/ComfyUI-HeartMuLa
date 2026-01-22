import { app } from "../../scripts/app.js";

// Import CSS
const link = document.createElement("link");
link.rel = "stylesheet";
link.type = "text/css";
link.href = new URL("./heartmula.css", import.meta.url).href;
document.head.appendChild(link);

const PRESETS = {
    gender: {
        title: "Vocal",
        items: ["Female", "Male", "Chorus"],
        multi: false,
        widget: "vocal_gender"
    },
    style: {
        title: "Style",
        items: ["pop", "rock", "R&B", "jazz", "electronic", "classical", "hip hop", "folk", "metal", "country", "blues", "reggae", "punk", "disco", "house", "techno", "trance", "dubstep", "ambient", "indie", "soul", "funk", "latin", "k-pop", "j-pop", "opera", "gospel"],
        multi: true,
        widget: "style_preset"
    },
    instrument: {
        title: "Instrument",
        items: ["piano", "violin", "ukulele", "djembe", "guitar", "drums", "bass", "synthesizer", "flute", "cello", "trumpet", "saxophone", "harp", "accordion", "banjo", "harmonica", "clarinet", "trombone", "organ", "bongo", "sitar"],
        multi: true,
        widget: "instrument_preset"
    }
};

app.registerExtension({
    name: "HeartMuLa.Node",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HeartMuLaGenerator") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                const node = this;

                // Helper to find widget by name
                const findWidget = (name) => node.widgets ? node.widgets.find(w => w.name === name) : null;

                // Hide original widgets
                ["vocal_gender", "style_preset", "instrument_preset"].forEach(name => {
                    const w = findWidget(name);
                    if (w) {
                        w.type = "converted-widget"; // Change type to avoid rendering
                        w.computeSize = () => [0, -4]; // Zero size
                        if (w.inputEl) w.inputEl.style.display = "none";
                        w.hidden = true;
                    }
                });

                // Create container
                const container = document.createElement("div");
                container.className = "heartmula-presets-container";

                // Create Tabs
                const tabsContainer = document.createElement("div");
                tabsContainer.className = "heartmula-tabs";
                container.appendChild(tabsContainer);

                // Create Content Area
                const contentArea = document.createElement("div");
                contentArea.className = "heartmula-content";
                
                // Stop wheel propagation to allow scrolling without zooming canvas
                contentArea.addEventListener("wheel", (e) => {
                    e.stopPropagation();
                }, { passive: false });
                
                // Stop pointer down propagation to allow text selection or other interactions
                contentArea.addEventListener("pointerdown", (e) => {
                   e.stopPropagation(); 
                }, { passive: false });

                container.appendChild(contentArea);

                // Store active state
                let activeTab = "style"; // Default to Style

                // Render logic
                const renderTab = (key, config) => {
                    const tab = document.createElement("div");
                    tab.className = `heartmula-tab ${activeTab === key ? "active" : ""}`;
                    tab.innerText = config.title;
                    
                    tab.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        activeTab = key;
                        
                        // Update tabs UI
                        Array.from(tabsContainer.children).forEach(t => t.classList.remove("active"));
                        tab.classList.add("active");
                        
                        // Update content UI
                        Array.from(contentArea.children).forEach(c => c.classList.remove("active"));
                        document.getElementById(`heartmula-tab-${key}`).classList.add("active");
                    };
                    
                    tabsContainer.appendChild(tab);
                };

                const renderContent = (key, config) => {
                    const content = document.createElement("div");
                    content.id = `heartmula-tab-${key}`;
                    content.className = `heartmula-tab-content ${activeTab === key ? "active" : ""}`;
                    
                    const grid = document.createElement("div");
                    grid.className = "heartmula-grid";
                    
                    const widget = findWidget(config.widget);
                    
                    config.items.forEach(item => {
                        const wrapper = document.createElement("div");
                        wrapper.className = `heartmula-checkbox-item ${!config.multi ? "heartmula-radio-item" : ""}`;
                        
                        const checkbox = document.createElement("div");
                        checkbox.className = "heartmula-checkbox-box";
                        
                        const label = document.createElement("div");
                        label.className = "heartmula-checkbox-label";
                        label.innerText = item;
                        label.title = item;
                        
                        wrapper.appendChild(checkbox);
                        wrapper.appendChild(label);
                        
                        // State check function
                        const updateState = () => {
                            if (!widget) return;
                            const currentVal = widget.value || "";
                            
                            if (config.multi) {
                                const vals = currentVal.split(",").map(s => s.trim());
                                if (vals.includes(item)) {
                                    wrapper.classList.add("selected");
                                } else {
                                    wrapper.classList.remove("selected");
                                }
                            } else {
                                if (currentVal === item) {
                                    wrapper.classList.add("selected");
                                } else {
                                    wrapper.classList.remove("selected");
                                }
                            }
                        };
                        
                        updateState();
                        
                        // Hook into widget callback to update UI when value changes externally
                        // We need a mechanism to update UI elements when the widget value changes
                        // We can attach a listener to the content element or just rely on re-rendering if we were using React
                        // Here we use a custom property on the widget to track listeners
                        if (!widget.uiListeners) widget.uiListeners = [];
                        widget.uiListeners.push(updateState);

                        // Click handler
                        wrapper.onclick = (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            
                            if (!widget) return;
                            
                            let newVal;
                            if (config.multi) {
                                const currentVal = widget.value || "";
                                let vals = currentVal ? currentVal.split(",").map(s => s.trim()).filter(s => s) : [];
                                
                                if (vals.includes(item)) {
                                    vals = vals.filter(v => v !== item);
                                } else {
                                    vals.push(item);
                                }
                                newVal = vals.join(",");
                                if (newVal === "") newVal = "None"; // Or empty string? Node logic handles None or empty
                            } else {
                                newVal = item;
                            }
                            
                            widget.value = newVal;
                            
                            // Trigger all listeners
                            if (widget.uiListeners) widget.uiListeners.forEach(l => l());
                            
                            // Trigger callback if exists
                            if (widget.callback) {
                                widget.callback(widget.value, app.canvas, node, widget.pos, e);
                            }
                            
                            app.graph.setDirtyCanvas(true, true);
                        };
                        
                        grid.appendChild(wrapper);
                    });
                    
                    content.appendChild(grid);
                    contentArea.appendChild(content);
                };

                // Initialize Tabs and Content
                Object.keys(PRESETS).forEach(key => {
                    renderTab(key, PRESETS[key]);
                    renderContent(key, PRESETS[key]);
                });
                
                // Override widget callbacks to trigger listeners
                ["vocal_gender", "style_preset", "instrument_preset"].forEach(name => {
                    const w = findWidget(name);
                    if (w) {
                        const originalCallback = w.callback;
                        w.callback = function(v) {
                             if (w.uiListeners) w.uiListeners.forEach(l => l());
                             if (originalCallback) originalCallback.apply(this, arguments);
                        };
                    }
                });

                // Add to node as DOM widget
                if (this.addDOMWidget) {
                    const domWidget = this.addDOMWidget("presets_ui", "html", container, {
                        serialize: false,
                        hideOnZoom: false
                    });
                    
                    // Move DOM widget to the top (index 0)
                    // We need to ensure it's the first widget in the list
                    // ComfyUI renders widgets in order
                    if (this.widgets && this.widgets.length > 0) {
                        const index = this.widgets.indexOf(domWidget);
                        if (index > 0) {
                            this.widgets.splice(index, 1);
                            this.widgets.unshift(domWidget);
                        }
                    }
                } else {
                    console.warn("HeartMuLa: addDOMWidget not supported on this node instance.");
                }
                
                // Force default size to accommodate the UI
                const currentSize = this.size;
                // Use a reasonable default size if not already set larger
                if (currentSize[0] < 800 || currentSize[1] < 800) {
                     this.setSize([Math.max(currentSize[0], 800), Math.max(currentSize[1], 800)]);
                }

                return r;
            };
        }
    }
});
