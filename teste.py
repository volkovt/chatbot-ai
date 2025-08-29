"""
LRU TTL Cache com persistência em disco.

Recursos:
- LRU (Least Recently Used) com OrderedDict.
- TTL por item (expiração automática).
- Persistência opcional em JSON (save/load e autosave em thread daemon).
- Context manager para salvar automaticamente ao sair.
- Demonstração de uso em __main__.

Obs.: os valores precisam ser serializáveis em JSON para persistência.
"""

from __future__ import annotations
from collections import OrderedDict
from typing import Any, Optional, Iterator, Tuple
import json
import time
import threading
import os
from pathlib import Path


class CacheExpired(KeyError):
    """Exceção para itens expirados."""


class PersistenceError(RuntimeError):
    """Exceção para falhas de persistência."""


class LRUCache:
    def __init__(
        self,
        capacity: int = 128,
        default_ttl: Optional[float] = None,
        persist_path: Optional[str | os.PathLike] = None,
        autosave_interval: float = 5.0,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity deve ser > 0")
        self.capacity = int(capacity)
        self.default_ttl = default_ttl
        self.persist_path = Path(persist_path) if persist_path else None
        self.autosave_interval = float(autosave_interval)

        # Armazena: key -> (value, expire_at | None)
        self._data: "OrderedDict[Any, Tuple[Any, Optional[float]]]" = OrderedDict()
        self._lock = threading.RLock()

        # Controle do autosave
        self._stop_evt = threading.Event()
        self._autosave_thread: Optional[threading.Thread] = None
        if self.persist_path:
            # Tenta carregar na inicialização
            if self.persist_path.exists():
                try:
                    self.load()
                except Exception as e:
                    raise PersistenceError(f"Falha ao carregar {self.persist_path}: {e}") from e
            if self.autosave_interval > 0:
                self._start_autosave()

    # -------------------- Infra de thread de autosave --------------------
    def _start_autosave(self) -> None:
        t = threading.Thread(target=self._autosave_loop, name="LRUCacheAutosave", daemon=True)
        self._autosave_thread = t
        t.start()

    def _autosave_loop(self) -> None:
        while not self._stop_evt.wait(self.autosave_interval):
            try:
                self.save()
            except Exception:
                # Silencia para não interromper a aplicação; em produção, logue isso.
                pass

    # -------------------- Operações utilitárias --------------------
    def _now(self) -> float:
        return time.time()

    def _evict_if_needed(self) -> None:
        while len(self._data) > self.capacity:
            self._data.popitem(last=False)

    def _is_expired_entry(self, expire_at: Optional[float]) -> bool:
        return expire_at is not None and expire_at <= self._now()

    def _purge_expired(self) -> None:
        # Remove todos expirados; custo O(n) eventual
        to_delete = []
        now = self._now()
        for k, (_, exp) in self._data.items():
            if exp is not None and exp <= now:
                to_delete.append(k)
        for k in to_delete:
            self._data.pop(k, None)

    # -------------------- API pública --------------------
    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            expire_at = self._now() + ttl if ttl is not None else (
                self._now() + self.default_ttl if self.default_ttl is not None else None
            )
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (value, expire_at)
            self._evict_if_needed()

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            if key not in self._data:
                if default is not None:
                    return default
                raise KeyError(key)
            value, expire_at = self._data[key]
            if self._is_expired_entry(expire_at):
                # Remove e lança erro, a menos que default tenha sido especificado
                self._data.pop(key, None)
                if default is not None:
                    return default
                raise CacheExpired(f"Item expirado: {key}")
            # Acesso recente move para o fim
            self._data.move_to_end(key)
            return value

    def pop(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            try:
                value = self.get(key)
            except (KeyError, CacheExpired):
                if default is not None:
                    return default
                raise
            self._data.pop(key, None)
            return value

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            if key not in self._data:
                return False
            _, exp = self._data[key]
            if self._is_expired_entry(exp):
                self._data.pop(key, None)
                return False
            return True

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._data)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def keys(self) -> Iterator[Any]:
        with self._lock:
            self._purge_expired()
            return iter(list(self._data.keys()))

    def items(self) -> Iterator[Tuple[Any, Any]]:
        with self._lock:
            self._purge_expired()
            return iter([(k, v) for k, (v, _) in self._data.items()])

    # -------------------- Persistência --------------------
    def save(self) -> None:
        if not self.persist_path:
            return
        with self._lock:
            to_dump = []
            for k, (v, exp) in self._data.items():
                # Ignora itens expirados ao salvar
                if self._is_expired_entry(exp):
                    continue
                to_dump.append({"key": k, "value": v, "expire_at": exp})
            tmp = self.persist_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(to_dump, ensure_ascii=False, indent=2))
            tmp.replace(self.persist_path)

    def load(self) -> None:
        if not self.persist_path or not self.persist_path.exists():
            return
        with self._lock:
            raw = json.loads(self.persist_path.read_text() or "[]")
            self._data.clear()
            now = self._now()
            for entry in raw:
                k = entry["key"]
                v = entry["value"]
                exp = entry["expire_at"]
                if exp is not None and exp <= now:
                    continue
                self._data[k] = (v, exp)
            # Evita ultrapassar a capacidade ao carregar
            self._evict_if_needed()

    # -------------------- Context Manager --------------------
    def close(self) -> None:
        self._stop_evt.set()
        if self._autosave_thread and self._autosave_thread.is_alive():
            self._autosave_thread.join(timeout=1.0)
        try:
            self.save()
        except Exception:
            pass

    def __enter__(self) -> "LRUCache":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -------------------- Representação --------------------
    def __repr__(self) -> str:
        with self._lock:
            return f"LRUCache(capacity={self.capacity}, size={len(self)}, default_ttl={self.default_ttl})"


# -------------------- Demonstração --------------------
def _demo() -> None:
    print(">>> Demonstração do LRUCache com TTL e persistência (arquivo: cache.json)")
    path = "cache.json"
    with LRUCache(capacity=3, default_ttl=2.0, persist_path=path, autosave_interval=1.0) as cache:
        cache.set("a", {"user": "diego"}, ttl=1.0)
        cache.set("b", [1, 2, 3])
        cache.set("c", "valor C")
        print("Tamanho inicial:", len(cache))
        time.sleep(1.2)
        # 'a' deve expirar
        print("'a' no cache?", "a" in cache)
        try:
            cache.get("a")
        except CacheExpired as e:
            print("Acesso a 'a':", e)

        # Acessa 'b' (vira mais recente), insere 'd' e força a remoção de LRU
        _ = cache.get("b")
        cache.set("d", "valor D")
        print("Chaves após inserir 'd':", list(cache.keys()))
        print("Itens atuais:", list(cache.items()))
        # Autosave rodará em background; close() salva novamente


if __name__ == "__main__":
    _demo()
