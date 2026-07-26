import time

from ambar.domain.audio import DB_CEILING, DB_FLOOR, LevelMeter


def test_silence_gives_floor_db():
    meter = LevelMeter()

    db = meter.update([0.0] * 100)

    assert db == DB_FLOOR


def test_empty_samples_give_floor_db():
    meter = LevelMeter()

    db = meter.update([])

    assert db == DB_FLOOR


def test_full_scale_signal_approaches_ceiling_over_time():
    meter = LevelMeter(attack_seconds=0.02, release_seconds=0.3)

    db = None
    for _ in range(20):
        db = meter.update([1.0, -1.0] * 50)
        time.sleep(0.01)

    assert db is not None
    assert db > DB_CEILING - 1.0


def test_level_does_not_jump_instantly_between_updates():
    meter = LevelMeter(attack_seconds=0.08, release_seconds=0.3)

    meter.update([0.0] * 100)
    db_after_first_loud_update = meter.update([1.0] * 100)

    # La ballistica evita que un unico fragmento ruidoso dispare el medidor
    # instantaneamente al maximo, incluso con ataque rapido.
    assert db_after_first_loud_update < DB_CEILING - 1.0


def test_release_is_slower_than_attack():
    # Subida: de silencio a fuerte.
    rising = LevelMeter(attack_seconds=0.05, release_seconds=0.4)
    rising.update([0.0] * 100)
    time.sleep(0.05)
    db_up = rising.update([1.0] * 100)

    # Bajada: de fuerte a silencio, mismo tiempo transcurrido.
    falling = LevelMeter(attack_seconds=0.05, release_seconds=0.4)
    falling.update([1.0] * 100)
    time.sleep(0.05)
    db_down = falling.update([0.0] * 100)

    # En el mismo intervalo, la subida (ataque rapido) avanza mas hacia su
    # objetivo que la bajada (liberacion lenta) hacia el suyo.
    up_progress = db_up - DB_FLOOR
    down_progress = DB_CEILING - db_down
    assert up_progress > down_progress
