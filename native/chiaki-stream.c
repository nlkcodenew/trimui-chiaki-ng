#include <SDL2/SDL.h>
#include <chiaki/base64.h>
#include <chiaki/controller.h>
#include <chiaki/ffmpegdecoder.h>
#include <chiaki/log.h>
#include <chiaki/opusdecoder.h>
#include <chiaki/session.h>

#include <libavutil/frame.h>
#include <libavutil/imgutils.h>
#include <libavutil/pixfmt.h>
#include <libswscale/swscale.h>

#include <errno.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define APP_NAME "trimui-chiaki-ng stream"
#define SCREEN_WIDTH 1280
#define SCREEN_HEIGHT 720

typedef struct {
    char host[256];
    char regist_key[CHIAKI_SESSION_AUTH_SIZE];
    uint8_t morning[16];
    bool ps5;
    unsigned int width;
    unsigned int height;
    unsigned int fps;
    unsigned int bitrate;
    unsigned int volume;
} StreamConfig;

typedef struct {
    ChiakiLog log;
    ChiakiSession session;
    ChiakiFfmpegDecoder decoder;
    ChiakiOpusDecoder opus;
    ChiakiControllerState controller_state;
    SDL_Window *window;
    SDL_Renderer *renderer;
    SDL_Texture *texture;
    SDL_GameController *controller;
    SDL_Joystick *joystick;
    SDL_AudioDeviceID audio_device;
    struct SwsContext *sws;
    AVFrame *converted;
    atomic_bool frame_ready;
    atomic_bool running;
    atomic_bool connected;
    atomic_int exit_code;
    unsigned int volume;
    bool session_initialized;
    bool session_started;
    bool decoder_initialized;
    bool opus_initialized;
    bool start_select_held;
    uint32_t start_select_since;
    uint64_t rendered_frames;
    uint64_t lost_frames;
    uint32_t audio_channels;
} StreamApp;

static StreamApp *signal_app;

static void native_log(ChiakiLogLevel level, const char *message, void *user)
{
    (void)user;
    const char *name = "INFO";
    if(level == CHIAKI_LOG_ERROR) name = "ERROR";
    else if(level == CHIAKI_LOG_WARNING) name = "WARN";
    else if(level == CHIAKI_LOG_DEBUG) name = "DEBUG";
    else if(level == CHIAKI_LOG_VERBOSE) name = "TRACE";
    fprintf(stdout, "[native] [%s] %s\n", name, message ? message : "");
    fflush(stdout);
}

static void stop_signal(int signal_number)
{
    (void)signal_number;
    if(signal_app)
        atomic_store(&signal_app->running, false);
}

static void trim(char *text)
{
    char *start = text;
    while(*start == ' ' || *start == '\t' || *start == '\r' || *start == '\n') start++;
    if(start != text) memmove(text, start, strlen(start) + 1);
    size_t length = strlen(text);
    while(length && (text[length - 1] == ' ' || text[length - 1] == '\t' || text[length - 1] == '\r' || text[length - 1] == '\n'))
        text[--length] = '\0';
}

static bool parse_uint(const char *text, unsigned int minimum, unsigned int maximum, unsigned int *value)
{
    char *end = NULL;
    errno = 0;
    unsigned long parsed = strtoul(text, &end, 10);
    if(errno || !end || *end || parsed < minimum || parsed > maximum) return false;
    *value = (unsigned int)parsed;
    return true;
}

static bool load_config(const char *path, StreamConfig *config)
{
    memset(config, 0, sizeof(*config));
    config->width = 1280;
    config->height = 720;
    config->fps = 30;
    config->bitrate = 8000;
    config->volume = 80;

    FILE *file = fopen(path, "r");
    if(!file) {
        fprintf(stderr, "[native] cannot open session file: %s\n", strerror(errno));
        return false;
    }
    char line[768];
    char rp_key[128] = {0};
    while(fgets(line, sizeof(line), file)) {
        char *separator = strchr(line, '=');
        if(!separator) continue;
        *separator = '\0';
        char *value = separator + 1;
        trim(line);
        trim(value);
        if(!strcmp(line, "host")) snprintf(config->host, sizeof(config->host), "%s", value);
        else if(!strcmp(line, "regist_key")) snprintf(config->regist_key, sizeof(config->regist_key), "%s", value);
        else if(!strcmp(line, "rp_key")) snprintf(rp_key, sizeof(rp_key), "%s", value);
        else if(!strcmp(line, "ps5")) config->ps5 = !strcmp(value, "1") || !strcasecmp(value, "true");
        else if(!strcmp(line, "width")) parse_uint(value, 320, 3840, &config->width);
        else if(!strcmp(line, "height")) parse_uint(value, 180, 2160, &config->height);
        else if(!strcmp(line, "fps")) parse_uint(value, 1, 120, &config->fps);
        else if(!strcmp(line, "bitrate")) parse_uint(value, 1000, 50000, &config->bitrate);
        else if(!strcmp(line, "volume")) parse_uint(value, 0, 100, &config->volume);
    }
    fclose(file);
    unlink(path);

    size_t morning_size = sizeof(config->morning);
    if(!config->host[0] || !config->regist_key[0] || strlen(config->regist_key) > 8 ||
       chiaki_base64_decode(rp_key, strlen(rp_key), config->morning, &morning_size) != CHIAKI_ERR_SUCCESS || morning_size != 16) {
        memset(rp_key, 0, sizeof(rp_key));
        fprintf(stderr, "[native] invalid or incomplete session file\n");
        return false;
    }
    memset(rp_key, 0, sizeof(rp_key));
    return true;
}

static void frame_available(ChiakiFfmpegDecoder *decoder, void *user)
{
    (void)decoder;
    StreamApp *app = user;
    atomic_store(&app->frame_ready, true);
}

static void audio_settings(uint32_t channels, uint32_t rate, void *user)
{
    StreamApp *app = user;
    SDL_AudioSpec wanted;
    SDL_zero(wanted);
    wanted.freq = (int)rate;
    wanted.format = AUDIO_S16SYS;
    wanted.channels = (Uint8)channels;
    wanted.samples = 1024;
    if(app->audio_device) SDL_CloseAudioDevice(app->audio_device);
    app->audio_device = SDL_OpenAudioDevice(NULL, 0, &wanted, NULL, 0);
    if(!app->audio_device) {
        fprintf(stderr, "[native] SDL audio open failed: %s\n", SDL_GetError());
        return;
    }
    app->audio_channels = channels;
    SDL_PauseAudioDevice(app->audio_device, 0);
    fprintf(stdout, "[native] audio ready: %u channels %u Hz\n", channels, rate);
    fflush(stdout);
}

static void audio_frame(int16_t *samples, size_t samples_count, void *user)
{
    StreamApp *app = user;
    if(!app->audio_device || !samples_count) return;
    if(SDL_GetQueuedAudioSize(app->audio_device) > 48000) SDL_ClearQueuedAudio(app->audio_device);
    size_t count = samples_count * (app->audio_channels ? app->audio_channels : 2);
    if(app->volume < 100) {
        for(size_t index = 0; index < count; index++)
            samples[index] = (int16_t)(((int32_t)samples[index] * (int32_t)app->volume) / 100);
    }
    SDL_QueueAudio(app->audio_device, samples, count * sizeof(int16_t));
}

static void session_event(ChiakiEvent *event, void *user)
{
    StreamApp *app = user;
    switch(event->type) {
        case CHIAKI_EVENT_CONNECTED:
            atomic_store(&app->connected, true);
            fprintf(stdout, "[native] Remote Play connected\n");
            fflush(stdout);
            break;
        case CHIAKI_EVENT_LOGIN_PIN_REQUEST:
            fprintf(stderr, "[native] console asks for a 4-digit user login passcode; unsupported in this test build\n");
            atomic_store(&app->exit_code, 12);
            atomic_store(&app->running, false);
            break;
        case CHIAKI_EVENT_RUMBLE:
            if(app->controller)
                SDL_GameControllerRumble(app->controller, (uint16_t)event->rumble.left << 8, (uint16_t)event->rumble.right << 8, 500);
            break;
        case CHIAKI_EVENT_QUIT:
            fprintf(stderr, "[native] session quit: %s%s%s\n",
                    chiaki_quit_reason_string(event->quit.reason),
                    event->quit.reason_str ? " - " : "",
                    event->quit.reason_str ? event->quit.reason_str : "");
            if(chiaki_quit_reason_is_error(event->quit.reason)) atomic_store(&app->exit_code, 11);
            atomic_store(&app->running, false);
            break;
        case CHIAKI_EVENT_VIDEO_FEC_FAILURE:
            fprintf(stderr, "[native] video FEC failure frame=%d idr=%d\n",
                    event->video_fec_failure.frame_index, event->video_fec_failure.idr_request_sent);
            break;
        default:
            break;
    }
}

static uint32_t controller_button(Uint8 button)
{
    switch(button) {
        case SDL_CONTROLLER_BUTTON_B: return CHIAKI_CONTROLLER_BUTTON_CROSS;
        case SDL_CONTROLLER_BUTTON_A: return CHIAKI_CONTROLLER_BUTTON_MOON;
        case SDL_CONTROLLER_BUTTON_Y: return CHIAKI_CONTROLLER_BUTTON_BOX;
        case SDL_CONTROLLER_BUTTON_X: return CHIAKI_CONTROLLER_BUTTON_PYRAMID;
        case SDL_CONTROLLER_BUTTON_DPAD_LEFT: return CHIAKI_CONTROLLER_BUTTON_DPAD_LEFT;
        case SDL_CONTROLLER_BUTTON_DPAD_RIGHT: return CHIAKI_CONTROLLER_BUTTON_DPAD_RIGHT;
        case SDL_CONTROLLER_BUTTON_DPAD_UP: return CHIAKI_CONTROLLER_BUTTON_DPAD_UP;
        case SDL_CONTROLLER_BUTTON_DPAD_DOWN: return CHIAKI_CONTROLLER_BUTTON_DPAD_DOWN;
        case SDL_CONTROLLER_BUTTON_LEFTSHOULDER: return CHIAKI_CONTROLLER_BUTTON_L1;
        case SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: return CHIAKI_CONTROLLER_BUTTON_R1;
        case SDL_CONTROLLER_BUTTON_LEFTSTICK: return CHIAKI_CONTROLLER_BUTTON_L3;
        case SDL_CONTROLLER_BUTTON_RIGHTSTICK: return CHIAKI_CONTROLLER_BUTTON_R3;
        case SDL_CONTROLLER_BUTTON_START: return CHIAKI_CONTROLLER_BUTTON_OPTIONS;
        case SDL_CONTROLLER_BUTTON_BACK: return CHIAKI_CONTROLLER_BUTTON_SHARE;
        case SDL_CONTROLLER_BUTTON_GUIDE: return CHIAKI_CONTROLLER_BUTTON_PS;
        default: return 0;
    }
}

static void set_button(StreamApp *app, uint32_t button, bool pressed)
{
    if(pressed) app->controller_state.buttons |= button;
    else app->controller_state.buttons &= ~button;
}

static void handle_controller_event(StreamApp *app, SDL_Event *event)
{
    bool changed = false;
    if(event->type == SDL_CONTROLLERBUTTONDOWN || event->type == SDL_CONTROLLERBUTTONUP) {
        uint32_t button = controller_button(event->cbutton.button);
        if(button) {
            set_button(app, button, event->type == SDL_CONTROLLERBUTTONDOWN);
            changed = true;
        }
    } else if(event->type == SDL_CONTROLLERAXISMOTION) {
        int16_t value = event->caxis.value;
        switch(event->caxis.axis) {
            case SDL_CONTROLLER_AXIS_LEFTX: app->controller_state.left_x = value; break;
            case SDL_CONTROLLER_AXIS_LEFTY: app->controller_state.left_y = value; break;
            case SDL_CONTROLLER_AXIS_RIGHTX: app->controller_state.right_x = value; break;
            case SDL_CONTROLLER_AXIS_RIGHTY: app->controller_state.right_y = value; break;
            case SDL_CONTROLLER_AXIS_TRIGGERLEFT:
                app->controller_state.l2_state = value > 0 ? (uint8_t)(value >> 7) : 0;
                break;
            case SDL_CONTROLLER_AXIS_TRIGGERRIGHT:
                app->controller_state.r2_state = value > 0 ? (uint8_t)(value >> 7) : 0;
                break;
            default: return;
        }
        changed = true;
    }
    if(changed && app->session_initialized)
        chiaki_session_set_controller_state(&app->session, &app->controller_state);
}

static uint32_t joystick_button(Uint8 button)
{
    switch(button) {
        case 1: return CHIAKI_CONTROLLER_BUTTON_CROSS;
        case 0: return CHIAKI_CONTROLLER_BUTTON_MOON;
        case 3: return CHIAKI_CONTROLLER_BUTTON_BOX;
        case 2: return CHIAKI_CONTROLLER_BUTTON_PYRAMID;
        case 4: return CHIAKI_CONTROLLER_BUTTON_L1;
        case 5: return CHIAKI_CONTROLLER_BUTTON_R1;
        case 8: return CHIAKI_CONTROLLER_BUTTON_SHARE;
        case 9: return CHIAKI_CONTROLLER_BUTTON_OPTIONS;
        case 10: return CHIAKI_CONTROLLER_BUTTON_PS;
        case 11: return CHIAKI_CONTROLLER_BUTTON_L3;
        case 12: return CHIAKI_CONTROLLER_BUTTON_R3;
        default: return 0;
    }
}

static void handle_joystick_event(StreamApp *app, SDL_Event *event)
{
    bool changed = false;
    if(event->type == SDL_JOYBUTTONDOWN || event->type == SDL_JOYBUTTONUP) {
        bool pressed = event->type == SDL_JOYBUTTONDOWN;
        if(event->jbutton.button == 6) app->controller_state.l2_state = pressed ? 255 : 0;
        else if(event->jbutton.button == 7) app->controller_state.r2_state = pressed ? 255 : 0;
        else {
            uint32_t button = joystick_button(event->jbutton.button);
            if(button) set_button(app, button, pressed);
        }
        changed = true;
    } else if(event->type == SDL_JOYAXISMOTION) {
        switch(event->jaxis.axis) {
            case 0: app->controller_state.left_x = event->jaxis.value; break;
            case 1: app->controller_state.left_y = event->jaxis.value; break;
            case 2: app->controller_state.right_x = event->jaxis.value; break;
            case 3: app->controller_state.right_y = event->jaxis.value; break;
            default: return;
        }
        changed = true;
    } else if(event->type == SDL_JOYHATMOTION) {
        uint8_t value = event->jhat.value;
        set_button(app, CHIAKI_CONTROLLER_BUTTON_DPAD_UP, value & SDL_HAT_UP);
        set_button(app, CHIAKI_CONTROLLER_BUTTON_DPAD_DOWN, value & SDL_HAT_DOWN);
        set_button(app, CHIAKI_CONTROLLER_BUTTON_DPAD_LEFT, value & SDL_HAT_LEFT);
        set_button(app, CHIAKI_CONTROLLER_BUTTON_DPAD_RIGHT, value & SDL_HAT_RIGHT);
        changed = true;
    }
    if(changed && app->session_initialized)
        chiaki_session_set_controller_state(&app->session, &app->controller_state);
}

static bool render_frame(StreamApp *app)
{
    int32_t frames_lost = 0;
    ChiakiFfmpegFrame decoded = chiaki_ffmpeg_decoder_pull_frame(&app->decoder, &frames_lost);
    if(!decoded.frame) return true;
    app->lost_frames += frames_lost > 0 ? (uint64_t)frames_lost : 0;
    AVFrame *frame = decoded.frame;
    AVFrame *display = frame;

    if(frame->format != AV_PIX_FMT_YUV420P && frame->format != AV_PIX_FMT_YUVJ420P) {
        app->sws = sws_getCachedContext(app->sws, frame->width, frame->height, frame->format,
                                       frame->width, frame->height, AV_PIX_FMT_YUV420P,
                                       SWS_FAST_BILINEAR, NULL, NULL, NULL);
        if(!app->sws) {
            fprintf(stderr, "[native] cannot convert video pixel format %d\n", frame->format);
            av_frame_free(&frame);
            return false;
        }
        if(!app->converted) {
            app->converted = av_frame_alloc();
            app->converted->format = AV_PIX_FMT_YUV420P;
            app->converted->width = frame->width;
            app->converted->height = frame->height;
            if(av_frame_get_buffer(app->converted, 32) < 0) {
                fprintf(stderr, "[native] cannot allocate converted frame\n");
                av_frame_free(&frame);
                return false;
            }
        }
        av_frame_make_writable(app->converted);
        sws_scale(app->sws, (const uint8_t * const *)frame->data, frame->linesize, 0, frame->height,
                  app->converted->data, app->converted->linesize);
        display = app->converted;
    }

    if(!app->texture) {
        app->texture = SDL_CreateTexture(app->renderer, SDL_PIXELFORMAT_IYUV,
                                         SDL_TEXTUREACCESS_STREAMING, display->width, display->height);
        if(!app->texture) {
            fprintf(stderr, "[native] SDL texture failed: %s\n", SDL_GetError());
            av_frame_free(&frame);
            return false;
        }
        fprintf(stdout, "[native] first video frame: %dx%d format=%d\n", display->width, display->height, frame->format);
        fflush(stdout);
    }
    if(SDL_UpdateYUVTexture(app->texture, NULL,
                            display->data[0], display->linesize[0],
                            display->data[1], display->linesize[1],
                            display->data[2], display->linesize[2]) != 0) {
        fprintf(stderr, "[native] texture update failed: %s\n", SDL_GetError());
        av_frame_free(&frame);
        return false;
    }
    int output_w = 0, output_h = 0;
    SDL_GetRendererOutputSize(app->renderer, &output_w, &output_h);
    SDL_Rect destination = {0, 0, output_w, output_h};
    double source_ratio = (double)display->width / display->height;
    double output_ratio = (double)output_w / output_h;
    if(output_ratio > source_ratio) {
        destination.w = (int)(output_h * source_ratio);
        destination.x = (output_w - destination.w) / 2;
    } else if(output_ratio < source_ratio) {
        destination.h = (int)(output_w / source_ratio);
        destination.y = (output_h - destination.h) / 2;
    }
    SDL_SetRenderDrawColor(app->renderer, 0, 0, 0, 255);
    SDL_RenderClear(app->renderer);
    SDL_RenderCopy(app->renderer, app->texture, NULL, &destination);
    SDL_RenderPresent(app->renderer);
    app->rendered_frames++;
    av_frame_free(&frame);
    return true;
}

static bool init_sdl(StreamApp *app)
{
    if(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER | SDL_INIT_HAPTIC) != 0) {
        fprintf(stderr, "[native] SDL init failed: %s\n", SDL_GetError());
        return false;
    }
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "linear");
    SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
    app->window = SDL_CreateWindow(APP_NAME, SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
                                   SCREEN_WIDTH, SCREEN_HEIGHT, SDL_WINDOW_FULLSCREEN_DESKTOP | SDL_WINDOW_SHOWN);
    if(!app->window) {
        fprintf(stderr, "[native] SDL window failed: %s\n", SDL_GetError());
        return false;
    }
    app->renderer = SDL_CreateRenderer(app->window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if(!app->renderer) app->renderer = SDL_CreateRenderer(app->window, -1, SDL_RENDERER_SOFTWARE);
    if(!app->renderer) {
        fprintf(stderr, "[native] SDL renderer failed: %s\n", SDL_GetError());
        return false;
    }
    SDL_SetRenderDrawColor(app->renderer, 0, 0, 0, 255);
    SDL_RenderClear(app->renderer);
    SDL_RenderPresent(app->renderer);

    for(int index = 0; index < SDL_NumJoysticks(); index++) {
        if(SDL_IsGameController(index)) {
            app->controller = SDL_GameControllerOpen(index);
            if(app->controller) {
                fprintf(stdout, "[native] controller: %s\n", SDL_GameControllerName(app->controller));
                break;
            }
        }
    }
    if(!app->controller && SDL_NumJoysticks() > 0) {
        app->joystick = SDL_JoystickOpen(0);
        if(app->joystick) fprintf(stdout, "[native] joystick fallback: %s\n", SDL_JoystickName(app->joystick));
    }
    fflush(stdout);
    return true;
}

static void cleanup(StreamApp *app)
{
    if(app->session_started) {
        chiaki_session_stop(&app->session);
        chiaki_session_join(&app->session);
        app->session_started = false;
    }
    if(app->session_initialized) chiaki_session_fini(&app->session);
    if(app->opus_initialized) chiaki_opus_decoder_fini(&app->opus);
    if(app->decoder_initialized) chiaki_ffmpeg_decoder_fini(&app->decoder);
    if(app->audio_device) SDL_CloseAudioDevice(app->audio_device);
    if(app->converted) av_frame_free(&app->converted);
    if(app->sws) sws_freeContext(app->sws);
    if(app->texture) SDL_DestroyTexture(app->texture);
    if(app->controller) SDL_GameControllerClose(app->controller);
    if(app->joystick) SDL_JoystickClose(app->joystick);
    if(app->renderer) SDL_DestroyRenderer(app->renderer);
    if(app->window) SDL_DestroyWindow(app->window);
    SDL_Quit();
}

int main(int argc, char **argv)
{
    if(argc != 2) {
        fprintf(stderr, "usage: chiaki-stream SESSION_FILE\n");
        return 2;
    }
    StreamConfig config;
    if(!load_config(argv[1], &config)) return 3;

    StreamApp app;
    memset(&app, 0, sizeof(app));
    app.volume = config.volume;
    atomic_init(&app.frame_ready, false);
    atomic_init(&app.running, true);
    atomic_init(&app.connected, false);
    atomic_init(&app.exit_code, 0);
    signal_app = &app;
    signal(SIGINT, stop_signal);
    signal(SIGTERM, stop_signal);

    ChiakiErrorCode error = chiaki_lib_init();
    if(error != CHIAKI_ERR_SUCCESS) {
        fprintf(stderr, "[native] chiaki init failed: %s\n", chiaki_error_string(error));
        return 4;
    }
    chiaki_log_init(&app.log, CHIAKI_LOG_INFO | CHIAKI_LOG_WARNING | CHIAKI_LOG_ERROR, native_log, NULL);
    if(!init_sdl(&app)) {
        cleanup(&app);
        return 5;
    }

    ChiakiCodec codec = config.ps5 ? CHIAKI_CODEC_H265 : CHIAKI_CODEC_H264;
    error = chiaki_ffmpeg_decoder_init(&app.decoder, &app.log, codec, config.fps, NULL, NULL, frame_available, &app);
    if(error != CHIAKI_ERR_SUCCESS) {
        fprintf(stderr, "[native] FFmpeg decoder init failed: %s\n", chiaki_error_string(error));
        cleanup(&app);
        return 6;
    }
    app.decoder_initialized = true;

    chiaki_opus_decoder_init(&app.opus, &app.log);
    app.opus_initialized = true;
    chiaki_opus_decoder_set_cb(&app.opus, audio_settings, audio_frame, &app);

    ChiakiConnectInfo connect_info;
    memset(&connect_info, 0, sizeof(connect_info));
    connect_info.ps5 = config.ps5;
    connect_info.host = config.host;
    memcpy(connect_info.regist_key, config.regist_key, sizeof(connect_info.regist_key));
    memcpy(connect_info.morning, config.morning, sizeof(connect_info.morning));
    connect_info.video_profile.width = config.width;
    connect_info.video_profile.height = config.height;
    connect_info.video_profile.max_fps = config.fps;
    connect_info.video_profile.bitrate = config.bitrate;
    connect_info.video_profile.codec = codec;
    connect_info.video_profile_auto_downgrade = true;
    connect_info.packet_loss_max = 0.1;
    connect_info.enable_idr_on_fec_failure = true;

    fprintf(stdout, "[native] starting LAN stream host=%s profile=%ux%u@%u %ukbps codec=%s\n",
            config.host, config.width, config.height, config.fps, config.bitrate,
            config.ps5 ? "H265" : "H264");
    fflush(stdout);
    memset(config.regist_key, 0, sizeof(config.regist_key));
    memset(config.morning, 0, sizeof(config.morning));

    error = chiaki_session_init(&app.session, &connect_info, &app.log);
    memset(connect_info.regist_key, 0, sizeof(connect_info.regist_key));
    memset(connect_info.morning, 0, sizeof(connect_info.morning));
    if(error != CHIAKI_ERR_SUCCESS) {
        fprintf(stderr, "[native] session init failed: %s\n", chiaki_error_string(error));
        cleanup(&app);
        return 7;
    }
    app.session_initialized = true;
    ChiakiAudioSink audio_sink;
    chiaki_opus_decoder_get_sink(&app.opus, &audio_sink);
    chiaki_session_set_audio_sink(&app.session, &audio_sink);
    chiaki_session_set_video_sample_cb(&app.session, chiaki_ffmpeg_decoder_video_sample_cb, &app.decoder);
    chiaki_session_set_event_cb(&app.session, session_event, &app);
    chiaki_controller_state_set_idle(&app.controller_state);

    error = chiaki_session_start(&app.session);
    if(error != CHIAKI_ERR_SUCCESS) {
        fprintf(stderr, "[native] session start failed: %s\n", chiaki_error_string(error));
        cleanup(&app);
        return 8;
    }
    app.session_started = true;

    SDL_Event event;
    while(atomic_load(&app.running)) {
        while(SDL_PollEvent(&event)) {
            if(event.type == SDL_QUIT || (event.type == SDL_KEYDOWN && event.key.keysym.sym == SDLK_ESCAPE)) {
                atomic_store(&app.running, false);
            } else if(app.controller && (event.type == SDL_CONTROLLERBUTTONDOWN || event.type == SDL_CONTROLLERBUTTONUP || event.type == SDL_CONTROLLERAXISMOTION)) {
                handle_controller_event(&app, &event);
            } else if(!app.controller && app.joystick && (event.type == SDL_JOYBUTTONDOWN || event.type == SDL_JOYBUTTONUP || event.type == SDL_JOYAXISMOTION || event.type == SDL_JOYHATMOTION)) {
                handle_joystick_event(&app, &event);
            }
        }
        bool start_select = (app.controller_state.buttons & CHIAKI_CONTROLLER_BUTTON_OPTIONS) &&
                            (app.controller_state.buttons & CHIAKI_CONTROLLER_BUTTON_SHARE);
        if(start_select && !app.start_select_held) {
            app.start_select_held = true;
            app.start_select_since = SDL_GetTicks();
        } else if(!start_select) {
            app.start_select_held = false;
        } else if(SDL_GetTicks() - app.start_select_since >= 1200) {
            fprintf(stdout, "[native] exit requested by START+SELECT\n");
            atomic_store(&app.running, false);
        }
        if(atomic_exchange(&app.frame_ready, false) && !render_frame(&app)) {
            atomic_store(&app.exit_code, 10);
            atomic_store(&app.running, false);
        }
        SDL_Delay(2);
    }

    fprintf(stdout, "[native] stopping; connected=%d rendered=%llu lost=%llu\n",
            atomic_load(&app.connected), (unsigned long long)app.rendered_frames,
            (unsigned long long)app.lost_frames);
    fflush(stdout);
    cleanup(&app);
    signal_app = NULL;
    return atomic_load(&app.exit_code);
}
