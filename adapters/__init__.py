from importlib import import_module

ADAPTERS = {
    "buaa": ("adapters.buaa_cs", "BuaaCsAdapter"),
    "buaa_soft": ("adapters.buaa_soft", "BuaaSoftAdapter"),
    "bjtu_cs": ("adapters.bjtu_cs", "BjtuCsAdapter"),
    "bupt_sice": ("adapters.bupt_sice", "BuptSiceAdapter"),
    "bupt_scs": ("adapters.bupt_scs", "BuptScsAdapter"),
    "csu_ai": ("adapters.csu_ai", "CsuAiAdapter"),
    "csu_ngce": ("adapters.csu_ngce", "CsuNgceAdapter"),
    "csu_ngce_phd": ("adapters.csu_ngce", "CsuNgcePhdAdapter"),
    "dlmu_ist": ("adapters.dlmu_ist", "DlmuIstAdapter"),
    "dlut_ice": ("adapters.dlut_ice", "DlutIceAdapter"),
    "ecnu_ieeic": ("adapters.ecnu_ieeic", "EcnuIeeicAdapter"),
    "jlu": ("adapters.jlu_sai", "JluSaiAdapter"),
    "muc_xingong": ("adapters.muc_xingong", "MucXingongAdapter"),
    "nankai_cc": ("adapters.nankai_cc", "NankaiCcAdapter"),
    "nankai_cs": ("adapters.nankai_cs", "NankaiCsAdapter"),
    "neu_cse": ("adapters.neu_cse", "NeuCseAdapter"),
    "hhu": ("adapters.hhu_cies", "HhuCiesAdapter"),
    "hfut_ci": ("adapters.hfut_ci", "HfutCiAdapter"),
    "hnu_csee": ("adapters.hnu_csee", "HnuCseeAdapter"),
    "nuaa": ("adapters.nuaa_ai_ei", "NuaaAiEiAdapter"),
    "sdu_cs": ("adapters.sdu_cs", "SduCsAdapter"),
    "sia_cas": ("adapters.sia_cas", "SiaCasAdapter"),
    "siat": ("adapters.siat_dsdw", "SiatDsdwAdapter"),
    "shanghaitech_sist": ("adapters.shanghaitech_sist", "ShanghaitechSistAdapter"),
    "suda_scst": ("adapters.suda_scst", "SudaScstAdapter"),
    "suda_scst_fulltime": ("adapters.suda_scst_fulltime", "SudaScstFulltimeAdapter"),
    "tju": ("adapters.tju_txgcx", "TjuTxgcxAdapter"),
    "tju_cs": ("adapters.tju_cs_sssds", "TjuCsSssdsAdapter"),
    "xmu_iai": ("adapters.xmu_iai", "XmuIaiAdapter"),
    "zju_oc": ("adapters.zju_oc", "ZjuOcAdapter"),
    "zuel_xagx": ("adapters.zuel_xagx", "ZuelXagxAdapter"),
}


def load_adapter(key: str):
    module_name, class_name = ADAPTERS[key]
    return getattr(import_module(module_name), class_name)
