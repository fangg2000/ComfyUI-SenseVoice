import {app} from "../../../scripts/app.js"

//app.registerExtension({
//    name: "comfy.voice.recorder",
//    init() {
//        const RecorderWidget = {
//            name: "RecorderWidget",
//            template: `<div class="recorder-control">
//                <button @click="startRecording" :disabled="isRecording">开始录音</button>
//                <button @click="stopRecording" :disabled="!isRecording">停止并保存</button>
//                <div class="status-indicator" :style="{backgroundColor: statusColor}"></div>
//            </div>`,
//            props: ["value", "onInput"],
//            data() {
//                return {
//                    isRecording: false,
//                    statusColor: "#ccc"
//                };
//            },
//            methods: {
//                startRecording() {
//                    this.isRecording = true;
//                    this.statusColor = "#ff4444";
//                    this.sendEvent("start");
//                },
//                stopRecording() {
//                    this.isRecording = false;
//                    this.statusColor = "#44ff44";
//                    this.sendEvent("stop");
//                },
//                sendEvent(type) {
//                    // 通过websocket发送事件
//                    const msg = {
//                        type: "recorder_event",
//                        data: {
//                            node_id: this.$root.node.id,
//                            action: type
//                        }
//                    };
//                    app.websocket.send(JSON.stringify(msg));
//                }
//            }
//        };
//
//        LiteGraph.registerNodeType({
//            class: "VoiceRecorder",
//            title: "🎤 Voice Recorder",
//            desc: "Interactive voice recording node",
//            type: "VoiceRecorder"
//        }, () => {
//            const node = LiteGraph.createNode("VoiceRecorder");
//
//            // 添加自定义widget
//            const widget = new LGraphWidget(node, {
//                widget: {
//                    type: "vue",
//                    component: RecorderWidget
//                }
//            });
//
//            node.addCustomWidget(widget);
//            return node;
//        });
//    }
//});

app.registerExtension({
    name: "comfy.button_node",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "VoiceRecorderNode") {
            console.log("API b:", app.graph);

            const originalOnCreated = nodeData.prototype.onNodeCreated || function(){};
            console.log("API c:", app.graph);

            // 使用传统函数保持this作用域
            nodeData.prototype.onNodeCreated = function() {
                console.log("API d:", app.graph);
                try {
                    const res = originalOnCreated.apply(this, arguments);

                    // 添加延迟确保DOM就绪
                    setTimeout(() => {
                        const btn = document.createElement("button");
                        btn.textContent = "测试按钮";
                        btn.onclick = () => alert("点击生效!");

                        // 使用官方UI类保持样式一致
                        btn.className = "comfy-menu-btn";
                        btn.style.marginTop = "5px";

                        // 使用标准添加方式
                        this.addDOMWidget("button_widget", btn);
                    }, 50); // 50ms延迟

                    return res;
                } catch(e) {
                    console.error("节点创建错误:", e);
                }
            };
        }
    }
});
