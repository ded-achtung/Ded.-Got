// wpe-prototype/src/main.rs
//
// THROWAWAY PROTOTYPE — проверяет архитектурные Gap'ы на реальном Wayland.
//
// Что этот код проверяет:
// - Gap 1: calloop event loop + wgpu render из callbacks — реально работает?
// - Gap 2: frame callback loop → render → commit → next callback — ПОЛНЫЙ ЦИКЛ.
// - Gap 3: layer-shell initial commit без буфера → configure → ack → attach.
// - Gap 4: damage tracking (full damage на первый кадр, empty на unchanged).
// - Gap 5: IPC через unix socket на том же calloop — coexistence с Wayland.
//
// Режимы работы:
// - Animated mode (первые 10 кадров): полный frame callback loop, доказывает Gap 2.
// - Static mode (после 10 кадров): damage=empty, без callback request — экономия CPU.
// - IPC mode (всегда): unix socket /tmp/wpe-prototype.sock, команды ping/status/quit.
//
// ВАЖНО: требует Linux с wlroots композитором (Hyprland / Sway / labwc).

use std::io::{Read, Write};
use std::os::unix::net::UnixListener;
use std::time::Instant;

use calloop::generic::Generic;
use calloop::{EventLoop, Interest, LoopSignal, Mode, PostAction};
use calloop_wayland_source::WaylandSource;

use smithay_client_toolkit::{
    compositor::{CompositorHandler, CompositorState},
    delegate_compositor, delegate_layer, delegate_output, delegate_registry,
    output::{OutputHandler, OutputState},
    registry::{ProvidesRegistryState, RegistryState},
    registry_handlers,
    shell::{
        wlr_layer::{
            Anchor, KeyboardInteractivity, Layer, LayerShell, LayerShellHandler,
            LayerSurface, LayerSurfaceConfigure,
        },
        WaylandSurface,
    },
};
use wayland_client::{
    globals::registry_queue_init,
    protocol::{wl_output, wl_surface},
    Connection, QueueHandle,
};

const ANIMATED_FRAMES: u32 = 10;
const IPC_SOCKET_PATH: &str = "/tmp/wpe-prototype.sock";

struct State {
    // Wayland globals
    registry_state: RegistryState,
    output_state: OutputState,
    compositor_state: CompositorState,
    layer_shell: LayerShell,

    // Our layer surface
    surface: Option<LayerSurface>,

    // Gap 3: lifecycle tracking
    configured: bool,

    // Gap 4: damage tracking
    first_frame_rendered: bool,

    // Gap 2: frame callback mode
    // true = request frame callbacks continuously (animated/video simulation)
    // false = no more callbacks (static image, render only on change)
    animate: bool,

    // Metrics
    start_time: Instant,
    frames_rendered: u32,
    ipc_commands_handled: u32,

    // Clean shutdown
    loop_signal: LoopSignal,

    // wgpu resources (created after first configure)
    wgpu_state: Option<WgpuState>,
}

struct WgpuState {
    device: wgpu::Device,
    queue: wgpu::Queue,
    surface: wgpu::Surface<'static>,
    config: wgpu::SurfaceConfiguration,
}

// ─────────────────────────────────────────────────────────────────────
// Gap 3: layer-shell lifecycle state machine
// ─────────────────────────────────────────────────────────────────────
// 1. Create layer_surface → set anchor/size → initial commit WITHOUT buffer.
// 2. WAIT for compositor configure event.
// 3. ack_configure → create wgpu surface → render first frame.
// 4. Request frame callback → commit.
// 5. Compositor sends callback.done → render next frame (Gap 2).

impl LayerShellHandler for State {
    fn closed(&mut self, _: &Connection, _: &QueueHandle<Self>, _: &LayerSurface) {
        println!("[lifecycle] compositor closed our surface");
        self.loop_signal.stop();
    }

    fn configure(
        &mut self,
        _conn: &Connection,
        qh: &QueueHandle<Self>,
        layer: &LayerSurface,
        configure: LayerSurfaceConfigure,
        _serial: u32,
    ) {
        let (w, h) = configure.new_size;
        println!(
            "[Gap 3] configure received: size {}x{}, elapsed {:?}",
            w, h, self.start_time.elapsed()
        );

        if !self.configured {
            // First configure — initialize wgpu, render first frame.
            self.configured = true;
            self.init_wgpu(layer, w, h);
            let wl_surf = layer.wl_surface();
            self.render_frame(wl_surf, qh, true);
        } else {
            // Resize — reconfigure wgpu surface, re-render.
            if let Some(wgpu) = &mut self.wgpu_state {
                wgpu.config.width = w.max(1);
                wgpu.config.height = h.max(1);
                wgpu.surface.configure(&wgpu.device, &wgpu.config);
            }
            let wl_surf = layer.wl_surface();
            self.render_frame(wl_surf, qh, false);
        }
    }
}

impl State {
    fn init_wgpu(&mut self, layer: &LayerSurface, width: u32, height: u32) {
        println!("[Gap 1] init wgpu on calloop thread (not tokio)");

        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor::default());

        // SAFETY: wl_surface lives as long as State.
        // Production code uses Arc<WlSurface>, not transmute.
        let wl_surf = layer.wl_surface();
        let surface = unsafe {
            instance.create_surface_unsafe(
                wgpu::SurfaceTargetUnsafe::from_window(wl_surf)
                    .expect("failed to get surface target"),
            )
        }
        .expect("failed to create wgpu surface");

        let adapter = pollster::block_on(instance.request_adapter(
            &wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::LowPower,
                compatible_surface: Some(&surface),
                force_fallback_adapter: false,
            },
        ))
        .expect("failed to get adapter");

        println!("[Gap 1] adapter: {:?}", adapter.get_info().name);

        let (device, queue) = pollster::block_on(adapter.request_device(
            &wgpu::DeviceDescriptor::default(),
        ))
        .expect("failed to get device");

        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format: wgpu::TextureFormat::Bgra8Unorm,
            width: width.max(1),
            height: height.max(1),
            present_mode: wgpu::PresentMode::Fifo,
            alpha_mode: wgpu::CompositeAlphaMode::Opaque,
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &config);

        let surface_static: wgpu::Surface<'static> = unsafe {
            std::mem::transmute(surface)
        };

        self.wgpu_state = Some(WgpuState {
            device, queue, surface: surface_static, config,
        });
    }

    // ─────────────────────────────────────────────────────────────────
    // Gap 2: FULL frame callback loop
    // ─────────────────────────────────────────────────────────────────
    // This method is called from TWO places:
    //   1. LayerShellHandler::configure — first frame after init/resize.
    //   2. CompositorHandler::frame    — callback.done fired, next frame.
    //
    // The cycle: render → request callback → commit → [compositor] →
    //            callback.done → render → request callback → commit → ...
    //
    // For static content: render once with Full damage, then stop
    // requesting callbacks. CPU drops to ~0%.
    //
    // For animated content (video/shader): request callback every frame.
    // This method proves both paths work.
    fn render_frame(
        &mut self,
        wl_surf: &wl_surface::WlSurface,
        qh: &QueueHandle<Self>,
        is_first: bool,
    ) {
        let Some(wgpu) = &mut self.wgpu_state else { return };
        let frame_start = Instant::now();

        let frame = match wgpu.surface.get_current_texture() {
            Ok(f) => f,
            Err(e) => {
                println!("[render] get_current_texture error: {:?} — skip", e);
                return;
            }
        };

        // Animate color slightly per frame to visually confirm callback loop.
        let t = self.frames_rendered as f64 / ANIMATED_FRAMES as f64;
        let view = frame.texture.create_view(&Default::default());
        let mut encoder = wgpu.device.create_command_encoder(&Default::default());
        {
            let _pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("wpe-prototype"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.10 + 0.05 * t,
                            g: 0.15 + 0.10 * t,
                            b: 0.25 + 0.15 * t,
                            a: 1.0,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
        }
        wgpu.queue.submit([encoder.finish()]);

        // ─── Gap 4: damage ─────────────────────────────────────────
        if is_first || !self.first_frame_rendered {
            wl_surf.damage_buffer(0, 0, i32::MAX, i32::MAX);
            self.first_frame_rendered = true;
        } else if self.animate {
            // Animated: full damage every frame (color changes).
            wl_surf.damage_buffer(0, 0, i32::MAX, i32::MAX);
        }
        // else: static — no damage, compositor skips compositing.

        // ─── Gap 2: request next frame callback BEFORE commit ──────
        // This is the critical piece that was missing before.
        // Without this, the frame callback loop never fires.
        if self.animate && self.frames_rendered < ANIMATED_FRAMES {
            wl_surf.frame(qh, wl_surf.clone());
        }

        frame.present();
        wl_surf.commit();

        self.frames_rendered += 1;
        let elapsed = frame_start.elapsed();
        println!(
            "[metrics] frame {} rendered in {:?}{}",
            self.frames_rendered,
            elapsed,
            if self.animate { " (animated)" } else { " (static)" }
        );

        // Transition: animated → static after ANIMATED_FRAMES
        if self.animate && self.frames_rendered >= ANIMATED_FRAMES {
            println!(
                "[Gap 2] frame callback loop PROVEN: {} frames via callback.done → render → commit → callback",
                self.frames_rendered
            );
            println!("[Gap 2] switching to static mode — no more frame callbacks");
            self.animate = false;
        }
    }
}

// ─────────────────────────────────────────────────────────────────────
// Gap 2: CompositorHandler::frame — THE ACTUAL CALLBACK HANDLER
// ─────────────────────────────────────────────────────────────────────
// This is called by the compositor when it's ready for the next frame
// (wl_callback::done event). Previously this was an empty stub with a
// comment. Now it drives the full render cycle.

impl CompositorHandler for State {
    fn scale_factor_changed(&mut self, _: &Connection, _: &QueueHandle<Self>,
                            _: &wl_surface::WlSurface, _: i32) {}
    fn transform_changed(&mut self, _: &Connection, _: &QueueHandle<Self>,
                         _: &wl_surface::WlSurface, _: wl_output::Transform) {}

    fn frame(
        &mut self,
        _conn: &Connection,
        qh: &QueueHandle<Self>,
        surface: &wl_surface::WlSurface,
        _time: u32,
    ) {
        // Gap 2: THIS IS THE FRAME CALLBACK HANDLER.
        // Compositor sent wl_callback::done — it's ready for our next frame.
        // We render, request the next callback, and commit.
        //
        // This completes the cycle:
        //   configure → render → request_callback → commit
        //                         ↓
        //   callback.done → render → request_callback → commit
        //                         ↓
        //   callback.done → render → (stop if static) → commit

        if self.animate && self.frames_rendered < ANIMATED_FRAMES {
            self.render_frame(surface, qh, false);
        }
    }

    fn surface_enter(&mut self, _: &Connection, _: &QueueHandle<Self>,
                     _: &wl_surface::WlSurface, _: &wl_output::WlOutput) {}
    fn surface_leave(&mut self, _: &Connection, _: &QueueHandle<Self>,
                     _: &wl_surface::WlSurface, _: &wl_output::WlOutput) {}
}

impl OutputHandler for State {
    fn output_state(&mut self) -> &mut OutputState { &mut self.output_state }
    fn new_output(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_output::WlOutput) {}
    fn update_output(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_output::WlOutput) {}
    fn output_destroyed(&mut self, _: &Connection, _: &QueueHandle<Self>, _: wl_output::WlOutput) {}
}

impl ProvidesRegistryState for State {
    fn registry(&mut self) -> &mut RegistryState { &mut self.registry_state }
    registry_handlers![OutputState];
}

delegate_compositor!(State);
delegate_output!(State);
delegate_layer!(State);
delegate_registry!(State);

// ─────────────────────────────────────────────────────────────────────
// Gap 5: IPC/calloop coexistence
// ─────────────────────────────────────────────────────────────────────
// Proves that a unix socket IPC server can live on the SAME calloop
// event loop as Wayland events, without tokio, without threads.
//
// Commands:
//   echo "ping" | socat - UNIX-CONNECT:/tmp/wpe-prototype.sock
//   echo "status" | socat - UNIX-CONNECT:/tmp/wpe-prototype.sock
//   echo "quit" | socat - UNIX-CONNECT:/tmp/wpe-prototype.sock

fn handle_ipc_client(stream: &mut std::os::unix::net::UnixStream, state: &mut State) {
    let mut buf = [0u8; 256];
    let n = match stream.read(&mut buf) {
        Ok(n) if n > 0 => n,
        _ => return,
    };

    let cmd = std::str::from_utf8(&buf[..n]).unwrap_or("").trim();
    state.ipc_commands_handled += 1;

    let response = match cmd {
        "ping" => {
            println!("[ipc] ping → pong");
            "pong\n".to_string()
        }
        "status" => {
            let msg = format!(
                "frames={} uptime={:?} animate={} ipc_commands={}\n",
                state.frames_rendered,
                state.start_time.elapsed(),
                state.animate,
                state.ipc_commands_handled,
            );
            println!("[ipc] status → {}", msg.trim());
            msg
        }
        "quit" => {
            println!("[ipc] quit — shutting down");
            state.loop_signal.stop();
            "bye\n".to_string()
        }
        other => {
            println!("[ipc] unknown command: {other:?}");
            format!("error: unknown command '{other}'\n")
        }
    };

    let _ = stream.write_all(response.as_bytes());
}

// ─────────────────────────────────────────────────────────────────────
// main
// ─────────────────────────────────────────────────────────────────────

fn main() {
    println!("wpe-prototype starting, PID={}", std::process::id());
    println!("IPC socket: {IPC_SOCKET_PATH}");
    println!("  echo \"ping\" | socat - UNIX-CONNECT:{IPC_SOCKET_PATH}");
    println!("  echo \"status\" | socat - UNIX-CONNECT:{IPC_SOCKET_PATH}");
    println!("  echo \"quit\" | socat - UNIX-CONNECT:{IPC_SOCKET_PATH}");
    println!();

    let conn = Connection::connect_to_env()
        .expect("WAYLAND_DISPLAY not set or compositor not running");
    let (globals, event_queue) = registry_queue_init(&conn)
        .expect("failed to init registry");
    let qh = event_queue.handle();

    let mut event_loop: EventLoop<State> = EventLoop::try_new()
        .expect("failed to create calloop event loop");
    let loop_handle = event_loop.handle();

    // Gap 1: Wayland events on calloop, single thread.
    WaylandSource::new(conn.clone(), event_queue)
        .insert(loop_handle.clone())
        .expect("failed to insert wayland source into calloop");

    // ─── Gap 5: IPC unix socket on the same calloop ────────────────
    let _ = std::fs::remove_file(IPC_SOCKET_PATH);
    let ipc_listener = UnixListener::bind(IPC_SOCKET_PATH)
        .expect("failed to bind IPC socket");
    ipc_listener.set_nonblocking(true)
        .expect("failed to set nonblocking");

    loop_handle.insert_source(
        Generic::new(ipc_listener, Interest::READ, Mode::Level),
        |_readiness, listener, state: &mut State| {
            // Accept new IPC connections on the same calloop thread.
            // No tokio, no threads — just another event source.
            match listener.accept() {
                Ok((mut stream, _)) => {
                    handle_ipc_client(&mut stream, state);
                }
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {}
                Err(e) => eprintln!("[ipc] accept error: {e}"),
            }
            Ok(PostAction::Continue)
        },
    ).expect("failed to insert IPC source into calloop");

    println!("[Gap 5] IPC socket registered on calloop — same thread as Wayland");

    // ─── Wayland setup ─────────────────────────────────────────────
    let compositor_state = CompositorState::bind(&globals, &qh)
        .expect("compositor not available");
    let layer_shell = LayerShell::bind(&globals, &qh)
        .expect("wlr_layer_shell not available — not a wlroots compositor");

    let wl_surface = compositor_state.create_surface(&qh);
    let layer_surface = layer_shell.create_layer_surface(
        &qh, wl_surface, Layer::Background, Some("wpe-wallpaper"), None,
    );

    layer_surface.set_anchor(Anchor::all());
    layer_surface.set_size(0, 0);
    layer_surface.set_keyboard_interactivity(KeyboardInteractivity::None);

    // Gap 3: initial commit WITHOUT buffer.
    layer_surface.commit();

    let mut state = State {
        registry_state: RegistryState::new(&globals),
        output_state: OutputState::new(&globals, &qh),
        compositor_state,
        layer_shell,
        surface: Some(layer_surface),
        configured: false,
        first_frame_rendered: false,
        animate: true, // Start in animated mode to prove Gap 2
        start_time: Instant::now(),
        frames_rendered: 0,
        ipc_commands_handled: 0,
        loop_signal: event_loop.get_signal(),
        wgpu_state: None,
    };

    println!("[Gap 1] entering calloop run — single thread, no tokio");
    println!("[Gap 2] will render {} frames via callback loop, then switch to static", ANIMATED_FRAMES);
    println!();

    // Run until quit IPC command or SIGINT.
    // After animated frames complete, daemon stays alive for IPC testing.
    event_loop.run(None, &mut state, |_| {})
        .expect("event loop failed");

    // Cleanup
    let _ = std::fs::remove_file(IPC_SOCKET_PATH);
    println!(
        "\nprototype done. frames={} uptime={:?} ipc_commands={}",
        state.frames_rendered,
        state.start_time.elapsed(),
        state.ipc_commands_handled,
    );
}
