import json
import os
import uuid
import logging

logger = logging.getLogger("SessionService")

class SessionService:
    def __init__(self, storage_path="sessions"):
        os.makedirs(storage_path, exist_ok=True)
        self.storage_path = storage_path

    def _path(self, chat_id):
        return os.path.join(self.storage_path, f"{chat_id}.json")

    def list_chats(self):
        return [
            fname.replace(".json", "")
            for fname in os.listdir(self.storage_path)
            if fname.endswith(".json")
        ]

    def create_chat(self):
        chat_id = str(uuid.uuid4())[:8]
        data = {"history": [], "files": [], "title": None, "file_states": {}}
        self._save(chat_id, data)
        return chat_id

    def get_file_active(self, chat_id, path):
        """Retorna True se o arquivo estiver ativo, False caso contrário."""
        data = self._load(chat_id)
        return data.get("file_states", {}).get(path, True)

    def set_file_active(self, chat_id, path, state: bool):
        """Define o estado ativo de um arquivo e salva na sessão."""
        data = self._load(chat_id)
        file_states = data.get("file_states")
        if file_states is None:
            data["file_states"] = file_states = {}
        file_states[path] = state
        self._save(chat_id, data)

    def remove_file_active(self, chat_id, path):
        """Remove o estado de um arquivo da sessão."""
        data = self._load(chat_id)
        file_states = data.get("file_states", {})
        if path in file_states:
            del file_states[path]
            data["file_states"] = file_states
            self._save(chat_id, data)

    def get_chat_title(self, chat_id):
        """Retorna o título salvo da sessão, ou None."""
        data = self._load(chat_id)
        return data.get("title")

    def rename_chat(self, chat_id, new_title):
        """Renomeia a sessão, salvando o novo título."""
        data = self._load(chat_id)
        data["title"] = new_title
        self._save(chat_id, data)
        logger.info(f"[SessionService] chat {chat_id} renomeado para '{new_title}'")

    def delete_chat(self, chat_id):
        try:
            os.remove(self._path(chat_id))
            logger.info(f"[SessionService] sessão {chat_id} deletada com sucesso")
        except Exception as e:
            logger.error(f"[SessionService] falha ao deletar sessão {chat_id}: {e}", exc_info=True)

    def load_history(self, chat_id):
        data = self._load(chat_id)
        return data["history"]

    def save_message(self, chat_id, msg):
        data = self._load(chat_id)
        data["history"].append(msg)
        self._save(chat_id, data)

    def add_file(self, chat_id, path):
        data = self._load(chat_id)
        data["files"].append(path)
        self._save(chat_id, data)


    def get_files(self, chat_id):
        data = self._load(chat_id)
        return data["files"]

    def _load(self, chat_id):
        try:
            with open(self._path(chat_id), "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("history", [])
                data.setdefault("files", [])
                data.setdefault("title", None)
                data.setdefault("file_states", {})
                return data
        except Exception as e:
            logger.error(f"[SessionService] falha ao carregar {chat_id}: {e}", exc_info=True)
            return {"history": [], "files": [], "title": None, "file_states": {}}

    def _save(self, chat_id, data):
        try:
            with open(self._path(chat_id), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[SessionService] falha ao salvar {chat_id}: {e}", exc_info=True)

    def remove_file(self, chat_id, path):
        """Remove um arquivo da sessão e salva."""
        try:
            data = self._load(chat_id)
            if path in data["files"]:
                data["files"].remove(path)
                self._save(chat_id, data)
                logger.info(f"[SessionService] arquivo removido da sessão {chat_id}: {path}")
            else:
                logger.warn(f"[SessionService] arquivo não encontrado na sessão {chat_id}: {path}")
        except Exception as e:
            logger.error(f"[SessionService] falha ao remover arquivo {path} da sessão {chat_id}: {e}", exc_info=True)
