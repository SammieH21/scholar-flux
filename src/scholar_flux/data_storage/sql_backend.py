import logging
from typing import Any, List, Dict, Optional
from sqlalchemy import create_engine, Column, String, Integer, JSON, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..utils.encoder import CacheDataEncoder
import base64
import cattrs

logger = logging.getLogger(__name__)

Base = declarative_base()

class CacheTable(Base):
    __tablename__ = 'cache'
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    cache = Column(JSON, nullable=False)

class SQLAlchemyCacheStorage:
    def __init__(self, db_url: str, echo: bool = False) -> None:
        self._initialize(url=db_url, echo=echo)

    def _initialize(self, **kws) -> None:
        self.engine = create_engine(**kws)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.converter = cattrs.Converter()

    @classmethod
    def encode_data(cls, data: Any, hash_prefix: Optional[str] ='<hashbytes>') -> Any:
        if isinstance(data, bytes):
            hash_prefix = hash_prefix or ''
            return hash_prefix + base64.b64encode(data).decode('utf-8')
        elif isinstance(data, dict):
            return {k: cls.encode_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.encode_data(item) for item in data]
        return data

    @classmethod
    def decode_data(cls, data: Any, hash_prefix='<hashbytes>') -> Any:
        if isinstance(data, str):
            # prefixes the hashbytes with the hash_prefix
            hash_prefix = hash_prefix or ''

            try:
                # checks if the data starts with the hash_prefix
                if data.startswith(hash_prefix):
                    # removes the hash_prefix and decodes the data
                    data = base64.b64decode(data.replace(hash_prefix, '', 1))

            except (ValueError, TypeError):
                logger.error(f"Error decoding data: {data}")
                pass

        elif isinstance(data, dict):
            return {k: cls.decode_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.decode_data(item) for item in data]

        return data

    def retrieve(self, key: str) -> Optional[Any]:
        session = self.Session()
        try:
            record = session.query(CacheTable).filter(CacheTable.key == key).first()
            if record:
                return CacheDataEncoder.decode(self.converter.structure(record.cache, Any))
            return None
        except exc.SQLAlchemyError as e:
            logger.error(f"Error retrieving key {key}: {e}")
            return None
        finally:
            session.close()

    def retrieve_all(self) -> Dict[str, Any]:
        session = self.Session()
        cache = {}
        try:
            records = session.query(CacheTable).all()
            cache = {record.key: CacheDataEncoder.encode(self.converter.structure(record.cache, Any)) for record in records}
        except exc.SQLAlchemyError as e:
            logger.error(f"Error retrieving all records: {e}")
        finally:
            session.close()
        return cache

    def retrieve_keys(self) -> List[str]:
        session = self.Session()
        try:
            keys = [record.key for record in session.query(CacheTable).all()]
        except exc.SQLAlchemyError as e:
            logger.error(f"Error retrieving keys: {e}")
            keys = []
        finally:
            session.close()
        return keys

    def update(self, key: str, data: Any) -> None:
        session = self.Session()
        try:
            structured_data = self.converter.unstructure(CacheDataEncoder.encode(data))
            record = session.query(CacheTable).filter(CacheTable.key == key).first()
            if record:
                record.cache = structured_data
            else:
                record = CacheTable(key=key, cache=structured_data)
                session.add(record)
            session.commit()
        except exc.SQLAlchemyError as e:
            logger.error(f"Error updating key {key}: {e}")
            session.rollback()
        finally:
            session.close()

    def delete(self, key: str) -> None:
        session = self.Session()
        try:
            record = session.query(CacheTable).filter(CacheTable.key == key).first()
            if record:
                session.delete(record)
                session.commit()
        except exc.SQLAlchemyError as e:
            logger.error(f"Error deleting key {key}: {e}")
            session.rollback()
        finally:
            session.close()

    def delete_all(self) -> None:
        session = self.Session()
        try:
            num_deleted = session.query(CacheTable).delete()
            session.commit()
            logger.debug(f"Deleted {num_deleted} records.")
        except exc.SQLAlchemyError as e:
            logger.error(f"Error deleting all records: {e}")
            session.rollback()
        finally:
            session.close()

