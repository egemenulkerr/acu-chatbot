# ============================================================================
# Cihaz kataloğu: onay bekleyen eşleşme ve çok adımlı arama akışı.
# chat.py sadece router ve genel orkestrasyonu tutar.
# ============================================================================

from __future__ import annotations

from typing import Optional

from ...schemas.chat import ChatResponse, ChatOption
from ...services.cache import cache_get, cache_set
from ...services.device_registry import (
    get_all_devices,
    get_device_info,
    search_device,
    search_devices_by_field,
    suggest_device,
)

CONFIRMATION_TTL: int = 300
DEVICE_SEARCH_TTL: int = 300

DEVICE_FILTER_OPTIONS: list[ChatOption] = [
    ChatOption(id="device_search_by_name", label="Cihaz adına göre"),
    ChatOption(id="device_search_by_unit", label="Birim / fakülteye göre"),
    ChatOption(id="device_search_by_lab", label="Laboratuvar adına göre"),
    ChatOption(id="device_search_by_owner", label="Sorumlu kişiye göre"),
]

_GENERAL_DEVICE_KEYWORDS: list[str] = [
    "cihazlar", "cihazları", "tüm cihaz", "hangi cihaz", "mevcut cihaz",
    "laboratuvar cihaz", "lab cihaz", "ne var", "neler var", "listele",
]


def cleanup_expired_confirmations() -> None:
    """Cache TTL tarafından otomatik yapıldığından no-op."""
    pass


def get_pending_device(session_id: str) -> Optional[str]:
    return cache_get(f"pending_device:{session_id}")


def set_pending_device(session_id: str, device_name: str) -> None:
    cache_set(f"pending_device:{session_id}", device_name, ttl=CONFIRMATION_TTL)


def get_device_search_state(session_id: str) -> Optional[dict]:
    return cache_get(f"device_search:{session_id}")


def set_device_search_state(session_id: str, state: dict) -> None:
    cache_set(f"device_search:{session_id}", state, ttl=DEVICE_SEARCH_TTL)


def clear_device_search_state(session_id: str) -> None:
    cache_set(f"device_search:{session_id}", None, ttl=1)


def get_confirmation_response(device_name: str) -> Optional[ChatResponse]:
    device_data: Optional[dict] = get_device_info(device_name)
    if device_data:
        info = device_data.get("info", {})
        return ChatResponse(
            response=(
                f"Anlaşıldı. İşte bilgiler:\n\n"
                f"**{device_data['name']}**\n\n"
                f"{info.get('description', '')}\n\n"
                f"{info.get('stock', '')}"
            ),
            source="Cihaz Katalogu (Onaylı)",
            intent_name="cihaz_bilgisi",
        )
    return None


def list_all_devices_response() -> ChatResponse:
    """Kayıtlı cihaz sayısı + arama seçenekleri. Session state çağıran tarafından set edilmelidir."""
    devices = get_all_devices()
    if not devices:
        return ChatResponse(
            response="Cihaz veritabanı henüz yüklenmedi. Lütfen biraz sonra tekrar deneyin.",
            source="Sistem",
            intent_name="cihaz_bilgisi_hata",
        )
    count = len(devices)
    return ChatResponse(
        response=(
            f"Şu anda katalogda **{count}** adet kayıtlı laboratuvar cihazı var.\n\n"
            "Aradığınız cihazı **hangi özellikle** aramak istersiniz?"
        ),
        source="Cihaz Katalogu",
        intent_name="cihaz_arama_secim",
        options=list(DEVICE_FILTER_OPTIONS),
    )


def handle_device_query(message: str, user_id: str) -> ChatResponse:
    msg_lower = message.lower()

    if any(kw in msg_lower for kw in _GENERAL_DEVICE_KEYWORDS):
        set_device_search_state(user_id, {"stage": "choose_filter"})
        return list_all_devices_response()

    device_data: Optional[dict] = search_device(message)
    if device_data:
        info = device_data.get("info", {})
        return ChatResponse(
            response=(
                f"**{device_data['name']}**\n\n"
                f"{info.get('description', '')}\n\n"
                f"{info.get('stock', '')}"
            ),
            source="Cihaz Katalogu",
            intent_name="cihaz_bilgisi",
        )

    suggestion: Optional[str] = suggest_device(message)
    if suggestion:
        set_pending_device(user_id, suggestion)
        return ChatResponse(
            response=f"Tam bulamadım ama şunu mu demek istediniz: **{suggestion.title()}**? (Evet/Hayır)",
            source="Akıllı Öneri Sistemi",
            intent_name="cihaz_bilgisi_onay",
        )

    return ChatResponse(
        response="Maalesef o cihazı bulamadım. Kayıtlı tüm cihazları görmek için 'cihazları listele' yazabilirsiniz.",
        source="Hata",
        intent_name="cihaz_bilgisi_hata",
    )


def handle_device_search_flow(user_id: str, raw_message: str) -> Optional[ChatResponse]:
    state = get_device_search_state(user_id)
    if not state:
        return None

    message = raw_message.strip()
    msg_lower = message.lower()
    stage = state.get("stage")

    if stage == "choose_filter":
        if "ad" in msg_lower or "isim" in msg_lower:
            set_device_search_state(user_id, {"stage": "provide_value", "filter": "name"})
            return ChatResponse(
                response="Tamam, cihaz adını yazar mısınız?",
                source="Cihaz Katalogu",
                intent_name="cihaz_arama_ad",
            )
        if "birim" in msg_lower or "fakülte" in msg_lower or "fakulte" in msg_lower:
            set_device_search_state(user_id, {"stage": "provide_value", "filter": "unit"})
            return ChatResponse(
                response="Tamam, aradığınız cihazın bağlı olduğu **birim/fakülte** adını yazar mısınız?",
                source="Cihaz Katalogu",
                intent_name="cihaz_arama_birim",
            )
        if "lab" in msg_lower or "laboratuvar" in msg_lower:
            set_device_search_state(user_id, {"stage": "provide_value", "filter": "lab"})
            return ChatResponse(
                response="Tamam, aradığınız cihazın bulunduğu **laboratuvar** adını yazar mısınız?",
                source="Cihaz Katalogu",
                intent_name="cihaz_arama_lab",
            )
        if "sorumlu" in msg_lower or "hoca" in msg_lower or "öğretim" in msg_lower or "ogretim" in msg_lower:
            set_device_search_state(user_id, {"stage": "provide_value", "filter": "owner"})
            return ChatResponse(
                response="Tamam, cihazdan sorumlu olduğunu düşündüğünüz **kişi adını** yazar mısınız?",
                source="Cihaz Katalogu",
                intent_name="cihaz_arama_sorumlu",
            )

        return ChatResponse(
            response=(
                "Nasıl aramak istediğinizi anlayamadım.\n\n"
                "Lütfen şu seçeneklerden birini yazın:\n"
                "- Cihaz adına göre\n"
                "- Birim / fakülteye göre\n"
                "- Laboratuvar adına göre\n"
                "- Sorumlu kişiye göre"
            ),
            source="Cihaz Katalogu",
            intent_name="cihaz_arama_secim",
            options=list(DEVICE_FILTER_OPTIONS),
        )

    if stage == "provide_value":
        filter_type = state.get("filter")
        devices = get_all_devices()
        matches: list[tuple[str, dict]] = []
        q = msg_lower

        if filter_type == "name":
            device = search_device(message)
            clear_device_search_state(user_id)
            if not device:
                return ChatResponse(
                    response="Bu ada yakın bir cihaz bulamadım. İsmi biraz daha net yazmayı deneyebilir misiniz?",
                    source="Cihaz Katalogu",
                    intent_name="cihaz_bilgisi_hata",
                )
            info = device.get("info", {})
            desc = info.get("description", "")
            stock = info.get("stock", "")
            price = info.get("price", "")
            return ChatResponse(
                response=(
                    f"**{device['name']}**\n\n"
                    f"{desc}\n\n"
                    f"{stock}\n{price}"
                ),
                source="Cihaz Katalogu",
                intent_name="cihaz_bilgisi",
            )

        field_map = {
            "unit": "unit",
            "lab": "lab",
            "owner": "responsible",
        }
        field = field_map.get(filter_type or "")
        if field:
            raw_matches = search_devices_by_field(field, message)
            matches = list(raw_matches.items())
        else:
            for key, data in devices.items():
                desc = str(data.get("description", "")).lower()
                if desc and q in desc:
                    matches.append((key, data))

        clear_device_search_state(user_id)

        if not matches:
            return ChatResponse(
                response="Bu kriterlere uyan kayıtlı bir cihaz bulamadım. Farklı bir anahtar kelimeyle tekrar deneyebilirsiniz.",
                source="Cihaz Katalogu",
                intent_name="cihaz_bilgisi_hata",
            )

        if len(matches) == 1:
            key, data = matches[0]
            name = data.get("original_name", key.title())
            desc = data.get("description", "")
            stock = data.get("stock", "")
            price = data.get("price", "")
            return ChatResponse(
                response=(
                    f"**{name}**\n\n"
                    f"{desc}\n\n"
                    f"{stock}\n{price}"
                ),
                source="Cihaz Katalogu",
                intent_name="cihaz_bilgisi",
            )

        lines = ["Birden fazla cihaz bulundu:\n"]
        for key, data in matches[:10]:
            name = data.get("original_name", key.title())
            desc = data.get("description", "")
            lines.append(f"- {name} — {desc}")
        if len(matches) > 10:
            lines.append(f"\n(toplam {len(matches)} sonuçtan ilk 10 tanesi gösterildi)")
        lines.append("\nBelirli bir cihaz hakkında detay için cihaz adını yazabilirsiniz.")

        return ChatResponse(
            response="\n".join(lines),
            source="Cihaz Katalogu",
            intent_name="cihaz_bilgisi_liste",
        )

    clear_device_search_state(user_id)
    return None
