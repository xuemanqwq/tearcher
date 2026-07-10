from adapters.buaa_cs import BuaaCsAdapter
from adapters.buaa_soft import BuaaSoftAdapter
from adapters.dlmu_ist import DlmuIstAdapter
from adapters.dlut_ice import DlutIceAdapter
from adapters.hhu_cies import HhuCiesAdapter
from adapters.jlu_sai import JluSaiAdapter
from adapters.nuaa_ai_ei import NuaaAiEiAdapter
from adapters.siat_dsdw import SiatDsdwAdapter
from adapters.tju_cs_sssds import TjuCsSssdsAdapter
from adapters.tju_txgcx import TjuTxgcxAdapter

ADAPTERS = {
    "buaa": BuaaCsAdapter,
    "buaa_soft": BuaaSoftAdapter,
    "dlmu_ist": DlmuIstAdapter,
    "dlut_ice": DlutIceAdapter,
    "jlu": JluSaiAdapter,
    "hhu": HhuCiesAdapter,
    "nuaa": NuaaAiEiAdapter,
    "siat": SiatDsdwAdapter,
    "tju": TjuTxgcxAdapter,
    "tju_cs": TjuCsSssdsAdapter,
}
