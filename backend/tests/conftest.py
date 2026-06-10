import pytest

from app import main
from app.config import Settings


@pytest.fixture(autouse=True)
def _reset_service():
    """각 테스트 후 서비스 싱글턴 초기화(테스트 간 상태 격리)."""
    main.set_service(None)
    main.set_geocoder(None)
    yield
    main.set_service(None)
    main.set_geocoder(None)


@pytest.fixture
def settings() -> Settings:
    return Settings()


def demo_route() -> list[tuple[float, float]]:
    """shade_engine 데모와 동일한 남북 경로(서편 고층 건물 픽스처에 대응)."""
    return [(37.49750 + i * 0.00015, 127.0270) for i in range(11)]
