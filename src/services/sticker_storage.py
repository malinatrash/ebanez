import json
import os
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class StickerStorage:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.stickers_file = os.path.join(data_dir, "stickers.json")
        logger.info(f"Инициализация StickerStorage: data_dir={data_dir}, stickers_file={self.stickers_file}")
        
        # Создаем директорию, если её нет
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logger.info(f"Создана директория {self.data_dir}")
        
        # Инициализируем пустой словарь стикеров
        self.stickers: Dict[str, List[str]] = {}
        
        # Загружаем существующие стикеры
        if os.path.exists(self.stickers_file):
            try:
                with open(self.stickers_file, 'r') as f:
                    content = f.read().strip()
                    if content:  # Проверяем, что файл не пустой
                        self.stickers = json.loads(content)
                        logger.info(f"Загружены стикеры из {self.stickers_file}")
                    else:
                        logger.info(f"Файл {self.stickers_file} пустой, используем пустой словарь")
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка при парсинге JSON из {self.stickers_file}: {e}")
                # Если файл поврежден, создаем новый
                self.save_stickers()
            except Exception as e:
                logger.error(f"Ошибка при загрузке стикеров из {self.stickers_file}: {e}")
        else:
            logger.info(f"Файл {self.stickers_file} не существует, создаем новый")
            self.save_stickers()
            
        logger.info(f"Загружено стикеров: {len(self.stickers)}")
        
    def save_stickers(self) -> bool:
        """Сохранить стикеры в файл"""
        try:
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir)
                logger.info(f"Создана директория {self.data_dir}")
                
            with open(self.stickers_file, 'w') as f:
                json.dump(self.stickers, f, indent=2, ensure_ascii=False)
                logger.info(f"Стикеры сохранены в {self.stickers_file}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении стикеров в {self.stickers_file}: {e}")
            return False
            
    def add_sticker(self, chat_id: int, sticker_id: str) -> bool:
        """Добавить новый стикер"""
        chat_id_str = str(chat_id)
        
        # Создаем список для чата, если его нет
        if chat_id_str not in self.stickers:
            self.stickers[chat_id_str] = []
            logger.info(f"Создан новый список стикеров для чата {chat_id}")
            
        # Добавляем стикер, если его еще нет
        if sticker_id not in self.stickers[chat_id_str]:
            self.stickers[chat_id_str].append(sticker_id)
            logger.info(f"Добавлен стикер {sticker_id} для чата {chat_id}")
            saved = self.save_stickers()
            if saved:
                logger.info(f"Стикер успешно сохранен, всего стикеров для чата {chat_id}: {len(self.stickers[chat_id_str])}")
            return saved
        else:
            logger.info(f"Стикер {sticker_id} уже существует для чата {chat_id}")
            return False
        
    def get_stickers(self, chat_id: int) -> List[str]:
        """Получить список стикеров для чата"""
        chat_id_str = str(chat_id)
        stickers = self.stickers.get(chat_id_str, [])
        logger.info(f"Получено {len(stickers)} стикеров для чата {chat_id}")
        return stickers
