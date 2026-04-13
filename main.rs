// wpe-prototype/src/main.rs
//
// THROWAWAY PROTOTYPE — ~250 строк.
// Задача: проверить 4 архитектурных Gap'а из SELF-AUDIT.md на реальном Wayland.
//
// Что этот код НЕ является:
// - Это не skeleton 0.1.
// - Это не wpe-compat.
// - Это не production архитектура.
// - Этот код выкидывается после измерений.
//
// Что этот код проверяет:
// - Gap 1: calloop event loop + wgpu render из callbacks — реально работает?
// - Gap 2: frame callback loop → render → commit → next callback — правильная модель?
// - Gap 3: layer-shell initial commit без буфера → configure → ack → attach — правильно?
// - Gap 4: damage tracking (full damage на первый кадр, empty на unchanged) — экономит CPU?
//
// ВАЖНО: этот код требует запуск на Linux с wlroots композитором (Hyprland / Sway / labwc).
// Он НЕ запустится в браузере, в WSL без WSLg, на macOS, в docker без Wayland socket.

use std::sync::Arc;
use std::time::Instant;

use calloop::{EventLoop, LoopSignal};
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

// ─────────────────────────────────────────────────────────────────────
// Gap 1 answer: calloop-first architecture
// ─────────────────────────────────────────────────────────────────────
// Main thread = calloop event loop.
// Wayland events приходят как calloop events (через calloop-wayland-source).
// wgpu render вызывается ИЗ callback'ов — тот же thread что Wayland.
// Никакого tokio. Никакого secondary thread. Простая модель.
//
// Если в 0.1 понадобится async I/O (IPC server) — tokio runtime на отдельном
// thread, mpsc канал для команд в calloop. Но это в wpe-daemon, не здесь.

struct State {
    // Wayland globals
    registry_state: RegistryState,
    output_state: OutputState,
    compositor_state: CompositorState,
    layer_shell: LayerShell,

    // Our layer surface (один на прототип, реальный daemon будет Vec)
    surface: Option<LayerSurface>,

    // Gap 3: lifecycle tracking
    // configured=false означает initial commit ещё не завершился.
    // Попытка attach буфера до configured=true = protocol error.
    configured: bool,

    // Gap 4: damage tracking
    // first_frame_rendered=false означает надо нарисовать полный кадр с full damage.
    // После первого кадра: для статики damage=empty (compositor не перерисовывает).
    first_frame_rendered: bool,

    // Метрики (Gap 6 из SELF-AUDIT — измерить реальные числа)
    start_time: Instant,
    frames_rendered: u32,

    // Clean shutdown
    loop_signal: LoopSignal,

    // wgpu resources (создаются после первого configure)
    wgpu_state: Option<WgpuState>,
}

struct WgpuState {
    device: wgpu::Device,
    queue: wgpu::Queue,
    surface: wgpu::Surface<'static>,
    config: wgpu::SurfaceConfiguration,
}

// ─────────────────────────────────────────────────────────────────────
// Gap 3 answer: layer-shell lifecycle state machine
// ─────────────────────────────────────────────────────────────────────
// Правильная последовательность (согласно wlr-layer-shell-unstable-v1):
//   1. Create layer_surface из wl_surface.
//   2. Set anchor/size/keyboard_interactivity.
//   3. surface.commit() — initial commit БЕЗ buffer.
//   4. [WAIT] compositor присылает configure event.
//   5. configure.ack() и сохранить размер.
//   6. Создать wgpu surface из wl_surface.
//   7. Render первый кадр с full damage.
//   8. [WAIT] frame callback done.
//   9. Render следующий кадр (или skip если статика).
//
// Нарушение этого порядка (например, attach buffer на шаге 3) = protocol kill.

impl LayerShellHandler for State {
    fn closed(&mut self, _: &Connection, _: &QueueHandle<Self>, _: &LayerSurface) {
        self.loop_signal.stop();
    }

    fn configure(
        &mut self,
        _conn: &Connection,
        _qh: &QueueHandle<Self>,
        layer: &LayerSurface,
        configure: LayerSurfaceConfigure,
        _serial: u32,
    ) {
        let (w, h) = configure.new_size;
        println!(
            "[Gap 3] configure received: size {}x{}, elapsed {:?}",
            w, h, self.start_time.elapsed()
        );

        // Первый configure — инициализируем wgpu.
        if !self.configured {
            self.configured = true;
            self.init_wgpu(layer, w, h);
            self.render_frame(layer, /* is_first */ true);
        } else {
            // Resize случай — переконфигурировать wgpu surface.
            if let Some(wgpu) = &mut self.wgpu_state {
                wgpu.config.width = w.max(1);
                wgpu.config.height = h.max(1);
                wgpu.surface.configure(&wgpu.device, &wgpu.config);
            }
            self.render_frame(layer, /* is_first */ false);
        }
    }
}

impl State {
    fn init_wgpu(&mut self, layer: &LayerSurface, width: u32, height: u32) {
        println!("[Gap 1] init wgpu on calloop thread (not tokio)");

        // pollster::block_on — дешёвый sync-over-async без tokio.
        // Это приемлемо: wgpu init случается один раз, не в hot path.
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor::default());

        // SAFETY: wl_surface живёт столько же сколько State.
        // В production коде это нужно оформить явно через Arc или lifetimes.
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
                // Gap не в SELF-AUDIT но важный: на ноутбуке с hybrid graphics
                // нужен LowPower (integrated GPU), не HighPerformance (discrete).
                // Wallpaper daemon не должен жечь батарею на статичной картинке.
                power_preference: wgpu::PowerPreference::LowPower,
                compatible_surface: Some(&surface),
                force_fallback_adapter: false,
            },
        ))
        .expect("failed to get adapter");

        let (device, queue) = pollster::block_on(adapter.request_device(
            &wgpu::DeviceDescriptor::default(),
        ))
        .expect("failed to get device");

        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format: wgpu::TextureFormat::Bgra8Unorm,
            width: width.max(1),
            height: height.max(1),
            present_mode: wgpu::PresentMode::Fifo,  // vsync
            alpha_mode: wgpu::CompositeAlphaMode::Opaque,
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &config);

        // Промежуточная безопасность: Surface<'static> через Box leak
        // подходит для прототипа. Production — Arc<WlSurface>.
        let surface_static: wgpu::Surface<'static> = unsafe {
            std::mem::transmute(surface)
        };

        self.wgpu_state = Some(WgpuState {
            device, queue, surface: surface_static, config,
        });
    }

    fn render_frame(&mut self, layer: &LayerSurface, is_first: bool) {
        let Some(wgpu) = &mut self.wgpu_state else { return };

        let frame_start = Instant::now();

        let frame = match wgpu.surface.get_current_texture() {
            Ok(f) => f,
            Err(e) => {
                println!("[Gap 1] get_current_texture error: {:?} — skip frame", e);
                return;
            }
        };

        let view = frame.texture.create_view(&Default::default());
        let mut encoder = wgpu.device.create_command_encoder(&Default::default());
        {
            let _pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("wpe-prototype solid color"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.15, g: 0.20, b: 0.30, a: 1.0,
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

        // ─────────────────────────────────────────────────────────────────
        // Gap 4 answer: damage tracking перед present
        // ─────────────────────────────────────────────────────────────────
        let wl_surf = layer.wl_surface();
        if is_first || !self.first_frame_rendered {
            // Полный damage на первый кадр.
            wl_surf.damage_buffer(0, 0, i32::MAX, i32::MAX);
            self.first_frame_rendered = true;
        } else {
            // Статика: пустой damage. Compositor не перерисовывает output.
            // Для video/shader здесь будет full damage каждый кадр.
        }

        // ─────────────────────────────────────────────────────────────────
        // Gap 2 answer: frame callback ПЕРЕД present
        // ─────────────────────────────────────────────────────────────────
        // Запрашиваем callback на следующий кадр. Compositor пришлёт done
        // когда готов нас снова принять — тогда и нарисуем следующий.
        // Для image backend в этом прототипе мы callback не используем
        // (статика не требует постоянных кадров), но production video
        // backend будет wire up FrameCallbackHandler.

        // На wayland-client API frame callback регистрируется перед commit:
        // let cb = wl_surf.frame(&qh, data);
        // После callback.done → render_frame(is_first=false).

        frame.present();

        // ─────────────────────────────────────────────────────────────────
        // Gap 3 answer: commit после attach+damage
        // ─────────────────────────────────────────────────────────────────
        // wgpu уже сделал attach внутри present(). Нам остаётся commit.
        wl_surf.commit();

        self.frames_rendered += 1;
        println!(
            "[metrics] frame {} rendered in {:?}",
            self.frames_rendered, frame_start.elapsed()
        );

        if self.frames_rendered >= 3 {
            // Для прототипа — рисуем 3 кадра и выходим.
            // Production daemon остаётся живым.
            println!(
                "[metrics] total runtime: {:?}, frames: {}",
                self.start_time.elapsed(), self.frames_rendered
            );
            self.loop_signal.stop();
        }
    }
}

// ─────────────────────────────────────────────────────────────────────
// Boilerplate: handlers для SCTK — нужно реализовать чтобы компилировалось
// ─────────────────────────────────────────────────────────────────────

impl CompositorHandler for State {
    fn scale_factor_changed(&mut self, _: &Connection, _: &QueueHandle<Self>,
                            _: &wl_surface::WlSurface, _: i32) {}
    fn transform_changed(&mut self, _: &Connection, _: &QueueHandle<Self>,
                         _: &wl_surface::WlSurface, _: wl_output::Transform) {}
    fn frame(&mut self, _: &Connection, _: &QueueHandle<Self>,
             _: &wl_surface::WlSurface, _: u32) {
        // Gap 2 hook: здесь production код запросил бы следующий кадр
        // для анимированного контента (video/shader).
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
// main — bootstrap прототипа
// ─────────────────────────────────────────────────────────────────────

fn main() {
    println!("wpe-prototype starting, PID={}", std::process::id());

    let conn = Connection::connect_to_env()
        .expect("WAYLAND_DISPLAY not set or compositor not running — \
                 this prototype requires a running wlroots compositor");
    let (globals, event_queue) = registry_queue_init(&conn)
        .expect("failed to init registry");
    let qh = event_queue.handle();

    let mut event_loop: EventLoop<State> = EventLoop::try_new()
        .expect("failed to create calloop event loop");
    let loop_handle = event_loop.handle();

    // Gap 1: WaylandSource интегрирует wayland queue в calloop.
    // Main thread, no threads, no tokio.
    WaylandSource::new(conn.clone(), event_queue)
        .insert(loop_handle)
        .expect("failed to insert wayland source into calloop");

    let compositor_state = CompositorState::bind(&globals, &qh)
        .expect("compositor not available");
    let layer_shell = LayerShell::bind(&globals, &qh)
        .expect("wlr_layer_shell not available — this compositor is not wlroots-based");

    let wl_surface = compositor_state.create_surface(&qh);
    let layer_surface = layer_shell.create_layer_surface(
        &qh, wl_surface, Layer::Background, Some("wpe-wallpaper"), None,
    );

    layer_surface.set_anchor(Anchor::all());
    layer_surface.set_size(0, 0);  // 0,0 = compositor решает (full output size)
    layer_surface.set_keyboard_interactivity(KeyboardInteractivity::None);

    // Gap 3: initial commit БЕЗ буфера. После этого compositor пришлёт configure.
    layer_surface.commit();

    let mut state = State {
        registry_state: RegistryState::new(&globals),
        output_state: OutputState::new(&globals, &qh),
        compositor_state,
        layer_shell,
        surface: Some(layer_surface),
        configured: false,
        first_frame_rendered: false,
        start_time: Instant::now(),
        frames_rendered: 0,
        loop_signal: event_loop.get_signal(),
        wgpu_state: None,
    };

    println!("[Gap 1] entering calloop run — single thread, no tokio");
    event_loop.run(None, &mut state, |_| {})
        .expect("event loop failed");

    println!("prototype done.");
}
