using UnityEngine;

/// <summary>
/// Drives all non-combat visuals for a Boat 000 tower:
/// <list type="bullet">
///   <item>Idle: continuous hull bob + rock, mast sway (out of phase per mast), sail/flag blendshape ripple cycles.</item>
///   <item>Placement: one-shot drop-from-above + splash ring + SFX played on the impact frame.</item>
///   <item>Shoot: one-shot cannon recoil (translation along barrel axis), muzzle smoke spawn, mast sway impulse, deck splash.</item>
/// </list>
///
/// Separation of concerns: <see cref="BoatAttack"/> decides WHEN to fire and aims the turret;
/// this component only renders the visual *reaction* to those events via <see cref="PlayShoot"/>
/// and <see cref="PlayPlacement"/>. Rest-pose transforms are captured in <see cref="Start"/> so
/// every animated offset is applied as (rest ± sin/impulse), making the math composable without
/// drift between frames.
///
/// Cloth (sails + flag) is animated via blendshapes baked in Blender: the single "Ripple" shape
/// key gets its weight driven by a sine here so the cycle is deterministic and costs one
/// SetBlendShapeWeight per frame per part.
/// </summary>
public class BoatAnimator : MonoBehaviour
{
    // VFX prefabs are wired on the Boat000 prefab in the editor; they are non-null
    // in normal gameplay. Null-checks throughout keep the component functional if a
    // user drops it onto a bare test object without the assets set up.
    [SerializeField] private GameObject splashRingPrefab;
    [SerializeField] private GameObject muzzleSmokePrefab;

    // Placing: lerping from the "dropped from 1.5m above" start to the final position.
    // Idle: default state — continuous bob/rock/sway runs every Update.
    private enum State { Placing, Idle }
    private State _state = State.Idle;

    // Cached part transforms. All lookups live under the "Turret" child so the whole
    // boat can yaw as one rigid body (see BoatAttack). If the prefab ever loses the
    // Turret wrapper we fall back to `transform` so the component still drives *something*.
    private Transform _hull, _mastFore, _mastMain, _cannonL, _cannonR;
    private SkinnedMeshRenderer _sailFore, _sailMain, _flag;

    // Rest poses captured at Start. Idle motion is layered on top of these, not
    // accumulated — that means we never have to subtract last-frame offsets.
    private Vector3 _hullRest;
    private Quaternion _hullRestRot, _mastForeRest, _mastMainRest;
    private Vector3 _cannonLRest, _cannonRRest;

    // Placement drop animation state.
    private float _placeT;
    private const float PlaceDuration = 0.6f;
    private Vector3 _placeStart, _placeEnd;
    private Vector3 _placeScaleStart = new Vector3(1.1f, 1.1f, 1.1f);
    private bool _splashFired;

    // Shoot recoil clock. Initialised to a large value in Start so the recoil curve
    // returns 0 until the first shot — no spurious flinch on the first Update.
    private float _shootT;
    private const float ShootDuration = 0.35f;

    // Decaying angular impulses added to mast sway on fire. MoveTowards(0) in Update bleeds them off.
    private float _mastForeImpulse, _mastMainImpulse;

    void Start()
    {
        // The FBX imports with a "Turret" empty under the root; if the prefab loses
        // that wrapper (e.g. someone flattened it) fall back to the root itself so
        // the animator still finds its parts directly beneath.
        var turret = transform.Find("Turret");
        if (turret == null) turret = transform;

        _hull     = turret.Find("Hull");
        _mastFore = turret.Find("MastFore");
        _mastMain = turret.Find("MastMain");
        _cannonL  = turret.Find("CannonPort_L");
        _cannonR  = turret.Find("CannonPort_R");

        var sf = turret.Find("SailFore");
        var sm = turret.Find("SailMain");
        var fl = turret.Find("Flag");
        if (sf != null) _sailFore = sf.GetComponent<SkinnedMeshRenderer>();
        if (sm != null) _sailMain = sm.GetComponent<SkinnedMeshRenderer>();
        if (fl != null) _flag     = fl.GetComponent<SkinnedMeshRenderer>();

        // Snapshot rest poses for every part we'll animate. Doing this here (not inline)
        // means idle animation is simply rest + offset, not a state machine.
        if (_hull     != null) { _hullRest = _hull.localPosition; _hullRestRot = _hull.localRotation; }
        if (_mastFore != null) _mastForeRest = _mastFore.localRotation;
        if (_mastMain != null) _mastMainRest = _mastMain.localRotation;
        if (_cannonL  != null) _cannonLRest = _cannonL.localPosition;
        if (_cannonR  != null) _cannonRRest = _cannonR.localPosition;

        // Large sentinel so RecoilCurve returns 0 until PlayShoot resets it.
        _shootT = 999f;
    }

    /// <summary>
    /// Triggers the placement drop animation. Call this immediately after the boat is
    /// spawned at its final water position — the boat is instantly teleported 1.5m up,
    /// lerps down over <see cref="PlaceDuration"/>, and plays the splash ring + SFX at impact.
    /// </summary>
    public void PlayPlacement()
    {
        _state = State.Placing;
        _placeT = 0f;
        _splashFired = false;

        // Remember the requested final position, then yank the boat up to the start.
        _placeEnd = transform.position;
        _placeStart = _placeEnd + Vector3.up * 1.5f;
        transform.position = _placeStart;

        // Slight scale-up during the drop gives a subtle "falling" parallax cue.
        transform.localScale = _placeScaleStart;
    }

    /// <summary>
    /// Triggers the fire-volley visual reaction: muzzle smoke at each cannon, a small
    /// deck splash at the hull, mast sway impulse, and starts the cannon recoil curve.
    /// Call once per volley from <see cref="BoatAttack.Fire"/>.
    /// </summary>
    public void PlayShoot()
    {
        _shootT = 0f;
        _mastForeImpulse = 2f;
        _mastMainImpulse = 2f;

        if (muzzleSmokePrefab != null && _cannonL != null)
            Instantiate(muzzleSmokePrefab, _cannonL.position, _cannonL.rotation);
        if (muzzleSmokePrefab != null && _cannonR != null)
            Instantiate(muzzleSmokePrefab, _cannonR.position, _cannonR.rotation);

        // Deck splash: small, short-lived ring at the boat's own position — suggests
        // the broadside jolting a little water from the hull. Reusing the splash-ring
        // prefab avoids a second VFX asset for a trivial variant.
        if (splashRingPrefab != null)
        {
            var ring = Instantiate(splashRingPrefab, transform.position, Quaternion.identity);
            var sr = ring.GetComponent<SplashRing>();
            if (sr != null) { sr.lifetime = 0.2f; sr.endScale = 0.5f; }
        }
    }

    void Update()
    {
        float t = Time.time;
        float dt = Time.deltaTime;

        // Placement lerp runs on its own clock and suppresses idle motion for its
        // duration, so the drop reads as a single clean movement rather than a
        // bobbing object also falling.
        if (_state == State.Placing)
        {
            _placeT += dt;
            float u = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(_placeT / PlaceDuration));
            transform.position = Vector3.Lerp(_placeStart, _placeEnd, u);
            transform.localScale = Vector3.Lerp(_placeScaleStart, Vector3.one, u);

            // Fire the splash + SFX slightly before the literal bottom (u=0.95) so
            // audio and visual leading edges align with the user's perception of impact.
            if (!_splashFired && u >= 0.95f)
            {
                _splashFired = true;
                if (splashRingPrefab != null) Instantiate(splashRingPrefab, _placeEnd, Quaternion.identity);
                SfxPlayer.PlayOneShot("SFX/boat_place", _placeEnd, 0.7f);
            }
            if (_placeT >= PlaceDuration) _state = State.Idle;
            return;
        }

        // ── Idle continuous motion ──────────────────────────────────────────────
        // Hull: small vertical bob (amplitude 0.05m) and a lazy roll around Z axis (~3°).
        // Different frequencies (1.4 / 1.0) de-sync the two so the motion reads as ocean.
        if (_hull != null)
        {
            _hull.localPosition = _hullRest + Vector3.up * Mathf.Sin(t * 1.4f) * 0.05f;
            _hull.localRotation = _hullRestRot * Quaternion.Euler(0f, 0f, Mathf.Sin(t * 1.0f) * 3f);
        }

        // Mast sway: idle sine PLUS a decaying shoot impulse (added by PlayShoot).
        // MoveTowards bleeds the impulse to 0 at 5 units/sec, so a value of 2 resolves in ~0.4s.
        _mastForeImpulse = Mathf.MoveTowards(_mastForeImpulse, 0f, dt * 5f);
        _mastMainImpulse = Mathf.MoveTowards(_mastMainImpulse, 0f, dt * 5f);

        // Phase offset (+1.7 rad on MastMain) so fore and main sway out of sync — feels alive.
        if (_mastFore != null)
            _mastFore.localRotation = _mastForeRest * Quaternion.Euler(0f, 0f, Mathf.Sin(t * 1.2f) * 1.5f + _mastForeImpulse);
        if (_mastMain != null)
            _mastMain.localRotation = _mastMainRest * Quaternion.Euler(0f, 0f, Mathf.Sin(t * 1.2f + 1.7f) * 1.5f + _mastMainImpulse);

        // Sail/flag cloth: blendshape weight cycles 0–100 over a sine. The flag runs
        // faster (3.0 Hz vs 2.0 Hz) because smaller cloth flutters at a higher
        // frequency in reality, and the +0.5 rad offset on SailMain keeps the two
        // sails from pumping in lockstep.
        if (_sailFore != null && _sailFore.sharedMesh.blendShapeCount > 0)
            _sailFore.SetBlendShapeWeight(0, (Mathf.Sin(t * 2.0f) * 0.5f + 0.5f) * 100f);
        if (_sailMain != null && _sailMain.sharedMesh.blendShapeCount > 0)
            _sailMain.SetBlendShapeWeight(0, (Mathf.Sin(t * 2.0f + 0.5f) * 0.5f + 0.5f) * 100f);
        if (_flag != null && _flag.sharedMesh.blendShapeCount > 0)
            _flag.SetBlendShapeWeight(0, (Mathf.Sin(t * 3.0f) * 0.5f + 0.5f) * 100f);

        // ── Cannon recoil ────────────────────────────────────────────────────────
        // Advances the recoil clock regardless of fire state — RecoilCurve returns 0
        // once we pass ShootDuration, so the cannons sit at rest until the next PlayShoot resets _shootT.
        _shootT += dt;
        if (_cannonL != null) _cannonL.localPosition = _cannonLRest + RecoilOffset(_cannonL) * RecoilCurve(_shootT);
        if (_cannonR != null) _cannonR.localPosition = _cannonRRest + RecoilOffset(_cannonR) * RecoilCurve(_shootT);
    }

    /// <summary>
    /// The direction a cannon recoils along. Each cannon's barrel points along its local +Z
    /// (the Blender cylinder's long axis); recoil is a backward kick along -Z in the
    /// cannon's local space, converted to the Turret space so the offset is correct even
    /// as the Turret yaws.
    /// </summary>
    private Vector3 RecoilOffset(Transform cannon)
    {
        // Unity's * operator on (Quaternion, Vector3) *rotates* the vector; you can't
        // negate the Quaternion directly. Vector3.back (i.e. -Z) gives the kickback
        // direction; rotating it by the cannon's local rotation expresses that kick in
        // the parent (Turret) space where localPosition lives.
        return cannon.localRotation * Vector3.back * 0.15f;
    }

    /// <summary>
    /// Piecewise recoil animation curve:
    /// 0 → 1 linearly over the first 50ms (sharp kickback), then 1 → 0 linearly over the
    /// remainder of ShootDuration (slow return). After ShootDuration it pins at 0 so the
    /// cannon rests at its authored position.
    /// </summary>
    private float RecoilCurve(float t)
    {
        if (t < 0.05f) return Mathf.Lerp(0f, 1f, t / 0.05f);
        if (t < ShootDuration) return Mathf.Lerp(1f, 0f, (t - 0.05f) / (ShootDuration - 0.05f));
        return 0f;
    }
}
