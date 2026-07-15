from adapters.buaa_cs import BuaaCsAdapter
from adapters.buaa_soft import BuaaSoftAdapter
from adapters.dlmu_ist import DlmuIstAdapter
from adapters.dlut_ice import DlutIceAdapter
from adapters.hhu_cies import HhuCiesAdapter
from adapters.jlu_sai import JluSaiAdapter
from adapters.nankai_cs import NankaiCsAdapter
from adapters.nuaa_ai_ei import NuaaAiEiAdapter
from adapters.sdu_cs import SduCsAdapter
from adapters.siat_dsdw import SiatDsdwAdapter
from adapters.tju_cs_sssds import TjuCsSssdsAdapter
from adapters.tju_txgcx import TjuTxgcxAdapter
from adapters.zuel_xagx import ZuelXagxAdapter

ADAPTERS = {
    "buaa": BuaaCsAdapter,
    "buaa_soft": BuaaSoftAdapter,
    "dlmu_ist": DlmuIstAdapter,
    "dlut_ice": DlutIceAdapter,
    "jlu": JluSaiAdapter,
    "nankai_cs": NankaiCsAdapter,
    "hhu": HhuCiesAdapter,
    "nuaa": NuaaAiEiAdapter,
    "sdu_cs": SduCsAdapter,
    "siat": SiatDsdwAdapter,
    "tju": TjuTxgcxAdapter,
    "tju_cs": TjuCsSssdsAdapter,
    "zuel_xagx": ZuelXagxAdapter,
}
