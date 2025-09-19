
// Room Lens — SuperCollider sketch (minimal)
// Boot server, create simple synthgraph, listen for OSC axes.

(
s.waitForBoot({
    ~axes = (
        grain_density: 5.0,
        filter_cutoff_hz: 1200,
        distortion_drive: 0.0,
        fm_index: 0.3,
        pitch_cluster_width_cents: 100,
        reverb_mix: 0.1,
        delay_time_ms: 220,
        env_attack_ms: 30,
        stereo_width: 0.5
    );

    // Simple synth: noisy grains + FM tone + delay + reverb
    SynthDef(\roomLens, { |out=0|
        var gden = LagControl.kr(\grain_density, 0.2);
        var cutoff = LagControl.kr(\filter_cutoff_hz, 0.2);
        var drive = LagControl.kr(\distortion_drive, 0.2);
        var fmidx = LagControl.kr(\fm_index, 0.2);
        var atk = LagControl.kr(\env_attack_ms, 0.2) / 1000;
        var dtime = LagControl.kr(\delay_time_ms, 0.2) / 1000;
        var mix = LagControl.kr(\reverb_mix, 0.5);

        var env = EnvGen.kr(Env.perc(atk, 0.3), Dust.kr(gden));
        var carrier = SinOsc.ar(200 + (LFNoise1.kr(1).range(-1,1) * \pitch_cluster_width_cents.kr(100)).cpsmidi.midicps, 0,
            env);
        var fm = SinOsc.ar(200, carrier * fmidx);

        var noise = BPF.ar(WhiteNoise.ar(0.2), cutoff.clip(200,8000), 0.2);
        var sig = (fm + noise) * (1 + drive).clip(0, 2);
        sig = tanh(sig * (1 + drive*4));

        sig = CombN.ar(sig, 0.6, dtime.clip(0.05,0.6), 2) * 0.7 + sig*0.6;
        sig = FreeVerb2.ar(sig, sig, mix, 0.6, 0.3);
        Out.ar(out, sig);
    }).add;

    ~synth = Synth(\roomLens);

    // OSC listener: /roomlens axes {key value ...}
    thisProcess.openUDPPort(57120);
    OSCdef(\axes, { |msg|
        // msg like: ['/roomlens', 'grain_density', 0.2, 'filter_cutoff_hz', 1000, ...]
        msg.drop(1).pairsDo({ |k, v|
            if(~axes[k.asSymbol].notNil) {
                ~axes[k.asSymbol] = v;
                ~synth.set(k.asSymbol, v);
            };
        });
    }, '/roomlens');

    "Room Lens SC ready.".postln;
});
)
