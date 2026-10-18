from bni_training.config import DataMode, Settings

from .csv_backend import CsvBackend
from .impala_backend import ImpalaBackend


def create_backend(settings: Settings):
    if settings.data_mode is DataMode.CSV:
        return CsvBackend(settings.csv_data_dir)
    return ImpalaBackend(settings)
