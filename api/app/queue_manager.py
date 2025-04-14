import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable, Optional
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileQueueManager:
    """
    Menedżer kolejki plików do anonimizacji.
    Zapewnia, że pliki są przetwarzane pojedynczo, jeden po drugim.
    """
    def __init__(self):
        self._queue_lock = asyncio.Lock()
        self._processing = False
        self._current_file_id = None
        self._queue = asyncio.Queue()
        self._results = {}
        self._start_time = None
        self._executor = ThreadPoolExecutor(max_workers=1)  # Tylko jeden wątek do przetwarzania
        self._failed_attempts = {}  # Licznik nieudanych prób dla każdego pliku
        
    async def add_to_queue(self, file_id: str, process_func: Callable[[str], Awaitable[Any]]) -> str:
        """
        Dodaje plik do kolejki przetwarzania.
        
        Args:
            file_id: Unikalny identyfikator pliku
            process_func: Funkcja asynchroniczna do przetworzenia pliku
            
        Returns:
            ID pliku w kolejce
        """
        logger.info(f"Dodawanie pliku {file_id} do kolejki")
        task = {
            "file_id": file_id,
            "process_func": process_func,
            "added_time": time.time()
        }
        
        await self._queue.put(task)
        
        # Jeśli nie ma aktualnie przetwarzanego pliku, rozpocznij przetwarzanie
        if not self._processing:
            # Uruchom przetwarzanie w tle
            asyncio.create_task(self._process_queue())
            
        return file_id
    
    async def get_status(self, file_id: str) -> Dict[str, Any]:
        """
        Sprawdza status przetwarzania pliku.
        
        Args:
            file_id: ID pliku
            
        Returns:
            Słownik zawierający informacje o statusie pliku:
            - status: 'queued', 'processing', 'completed' lub 'error'
            - position: pozycja w kolejce (tylko dla status='queued')
            - estimated_wait_time: szacowany czas oczekiwania w sekundach (tylko dla status='queued')
            - processing_time: czas przetwarzania w sekundach (tylko dla status='processing')
            - result: wynik przetwarzania (tylko dla status='completed')
            - error: komunikat błędu (tylko dla status='error')
        """
        # Sprawdź, czy plik jest w wynikach (zakończony lub błąd)
        if file_id in self._results:
            result = self._results[file_id]
            
            # Sprawdź, czy wynik zawiera błąd
            if isinstance(result, dict) and "error" in result:
                return {
                    "status": "error",
                    "error": result["error"]
                }
            
            # Jeśli nie ma błędu, to plik został pomyślnie przetworzony
            return {
                "status": "completed",
                "result": result
            }
        
        # Sprawdź, czy plik jest aktualnie przetwarzany
        if self._current_file_id == file_id:
            processing_time = time.time() - self._start_time if self._start_time else 0
            return {
                "status": "processing",
                "processing_time": processing_time
            }
        
        # Sprawdź, czy plik jest w kolejce
        position = await self._get_queue_position(file_id)
        if position is not None:
            # Szacujemy czas oczekiwania na podstawie pozycji w kolejce
            # Zakładamy, że każdy plik zajmuje średnio 30 sekund
            estimated_wait_time = position * 30
            return {
                "status": "queued",
                "position": position,
                "estimated_wait_time": estimated_wait_time
            }
        
        # Sprawdź, czy plik jest w trakcie ponownych prób
        if file_id in self._failed_attempts:
            attempts = self._failed_attempts[file_id]
            return {
                "status": "processing",
                "attempts": attempts,
                "max_attempts": 5
            }
        
        # Jeśli plik nie został znaleziony, zwracamy None
        return None
    
    async def get_result(self, file_id: str, timeout: int = 3600) -> Optional[Any]:
        """
        Pobiera wynik przetwarzania pliku.
        
        Args:
            file_id: ID pliku
            timeout: Maksymalny czas oczekiwania w sekundach
            
        Returns:
            Wynik przetwarzania lub None, jeśli plik jeszcze nie został przetworzony
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if file_id in self._results:
                # Kopiujemy wynik zamiast go usuwać, aby umożliwić wielokrotne pobranie
                # Wyniki będą usuwane po 24 godzinach przez osobny proces czyszczący
                result = self._results[file_id]
                return result
            
            # Jeśli plik jest aktualnie przetwarzany, poczekaj
            if self._current_file_id == file_id:
                processing_time = time.time() - self._start_time if self._start_time else 0
                logger.info(f"Plik {file_id} jest aktualnie przetwarzany (czas: {processing_time:.2f}s), oczekiwanie...")
            else:
                position = await self._get_queue_position(file_id)
                if position is not None:
                    logger.info(f"Plik {file_id} jest w kolejce na pozycji {position}, oczekiwanie...")
                else:
                    # Sprawdź, czy plik jest w trakcie ponownych prób
                    if file_id in self._failed_attempts:
                        attempts = self._failed_attempts[file_id]
                        logger.info(f"Plik {file_id} jest w trakcie ponownych prób (próba {attempts}/3), oczekiwanie...")
                    else:
                        logger.warning(f"Plik {file_id} nie został znaleziony w kolejce ani wynikach")
                        return None
            
            # Poczekaj chwilę przed ponownym sprawdzeniem
            await asyncio.sleep(1)
            
        logger.error(f"Przekroczono limit czasu oczekiwania na przetworzenie pliku {file_id}")
        return None
    
    async def _get_queue_position(self, file_id: str) -> Optional[int]:
        """Sprawdza pozycję pliku w kolejce."""
        position = 0
        for item in self._queue._queue:
            if item["file_id"] == file_id:
                return position
            position += 1
        return None
    
    async def _process_queue(self):
        """Przetwarza pliki z kolejki jeden po drugim z dodatkową ochroną przed błędami."""
        async with self._queue_lock:
            if self._processing:
                logger.info("Kolejka jest już przetwarzana, pomijam...")
                return
            self._processing = True
            logger.info("Rozpoczynam przetwarzanie kolejki...")
        
        try:
            while not self._queue.empty():
                task = await self._queue.get()
                file_id = task["file_id"]
                process_func = task["process_func"]
                wait_time = time.time() - task["added_time"]
                
                logger.info(f"Rozpoczynanie przetwarzania pliku {file_id} (czas oczekiwania: {wait_time:.2f}s)")
                self._current_file_id = file_id
                self._start_time = time.time()
                
                # Maksymalna liczba prób przetwarzania pliku
                max_attempts = 5  # Zwiększamy maksymalną liczbę prób
                current_attempt = self._failed_attempts.get(file_id, 0) + 1
                self._failed_attempts[file_id] = current_attempt
                
                logger.info(f"Próba przetwarzania pliku {file_id}: {current_attempt}/{max_attempts}")
                
                if current_attempt > max_attempts:
                    logger.error(f"Przekroczono maksymalną liczbę prób ({max_attempts}) dla pliku {file_id}")
                    self._results[file_id] = {"error": f"Przekroczono maksymalną liczbę prób ({max_attempts})"}
                    self._queue.task_done()
                    continue
                
                try:
                    # Wywołanie funkcji przetwarzającej z timeoutem
                    try:
                        # Używamy executor do uruchomienia funkcji asynchronicznej z bardzo długim timeoutem
                        result = await asyncio.wait_for(
                            process_func(file_id),
                            timeout=1800  # 30 minut na przetworzenie pliku
                        )
                        
                        processing_time = time.time() - self._start_time
                        logger.info(f"Zakończono przetwarzanie pliku {file_id} (czas: {processing_time:.2f}s)")
                        
                        # Zapisz wynik i usuń licznik błędów
                        self._results[file_id] = result
                        if file_id in self._failed_attempts:
                            del self._failed_attempts[file_id]
                            
                    except asyncio.TimeoutError:
                        logger.error(f"Przekroczono czas przetwarzania pliku {file_id}")
                        self._results[file_id] = {"error": "Przekroczono czas przetwarzania"}
                        
                except Exception as e:
                    logger.error(f"Błąd podczas przetwarzania pliku {file_id}: {str(e)}")
                    logger.error(traceback.format_exc())
                    
                    # Jeśli to nie jest ostatnia próba, dodaj plik ponownie do kolejki
                    if current_attempt < max_attempts:
                        logger.info(f"Ponowna próba przetwarzania pliku {file_id} (próba {current_attempt}/{max_attempts})")
                        # Dodajemy dłuższe opóźnienie przed ponowną próbą
                        delay = 5 * current_attempt  # Zwiększamy opóźnienie z każdą próbą (5s, 10s, 15s, 20s)
                        logger.info(f"Oczekiwanie {delay}s przed ponowną próbą...")
                        await asyncio.sleep(delay)
                        # Dodajemy zadanie na koniec kolejki
                        await self._queue.put(task)
                        logger.info(f"Zadanie {file_id} dodane ponownie do kolejki")
                    else:
                        self._results[file_id] = {"error": str(e)}
                finally:
                    self._current_file_id = None
                    self._queue.task_done()
        finally:
            async with self._queue_lock:
                self._processing = False
                if not self._queue.empty():
                    # Jeśli w międzyczasie pojawiły się nowe pliki, kontynuuj przetwarzanie
                    asyncio.create_task(self._process_queue())

# Singleton - jedna instancja menedżera kolejki dla całej aplikacji
queue_manager = FileQueueManager()
