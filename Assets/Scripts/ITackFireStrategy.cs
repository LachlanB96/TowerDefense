public interface ITackFireStrategy
{
    void OnStart(TackAttack tack);
    bool TryFire(TackAttack tack);
}
