from adapters.buaa_cs import BuaaCsAdapter
from adapters.buaa_soft import BuaaSoftAdapter
from adapters.csu_ai import CsuAiAdapter
from adapters.dlmu_ist import DlmuIstAdapter
from adapters.dlut_ice import DlutIceAdapter
from adapters.ecnu_ieeic import EcnuIeeicAdapter
from adapters.hhu_cies import HhuCiesAdapter
from adapters.hfut_ci import HfutCiAdapter
from adapters.jlu_sai import JluSaiAdapter
from adapters.muc_xingong import MucXingongAdapter
from adapters.nankai_cs import NankaiCsAdapter
from adapters.neu_cse import NeuCseAdapter
from adapters.nuaa_ai_ei import NuaaAiEiAdapter
from adapters.sdu_cs import SduCsAdapter
from adapters.sia_cas import SiaCasAdapter
from adapters.siat_dsdw import SiatDsdwAdapter
from adapters.shanghaitech_sist import ShanghaitechSistAdapter
from adapters.suda_scst import SudaScstAdapter
from adapters.tju_cs_sssds import TjuCsSssdsAdapter
from adapters.tju_txgcx import TjuTxgcxAdapter
from adapters.zju_oc import ZjuOcAdapter
from adapters.zuel_xagx import ZuelXagxAdapter

ADAPTERS = {
    "buaa": BuaaCsAdapter,
    "buaa_soft": BuaaSoftAdapter,
    "csu_ai": CsuAiAdapter,
    "dlmu_ist": DlmuIstAdapter,
    "dlut_ice": DlutIceAdapter,
    "ecnu_ieeic": EcnuIeeicAdapter,
    "jlu": JluSaiAdapter,
    "muc_xingong": MucXingongAdapter,
    "nankai_cs": NankaiCsAdapter,
    "neu_cse": NeuCseAdapter,
    "hhu": HhuCiesAdapter,
    "hfut_ci": HfutCiAdapter,
    "nuaa": NuaaAiEiAdapter,
    "sdu_cs": SduCsAdapter,
    "sia_cas": SiaCasAdapter,
    "siat": SiatDsdwAdapter,
    "shanghaitech_sist": ShanghaitechSistAdapter,
    "suda_scst": SudaScstAdapter,
    "tju": TjuTxgcxAdapter,
    "tju_cs": TjuCsSssdsAdapter,
    "zju_oc": ZjuOcAdapter,
    "zuel_xagx": ZuelXagxAdapter,
}
