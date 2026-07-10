"""実機クラスとモッククラスのインターフェース一貫性を検証するテスト。"""
from __future__ import annotations

import inspect
from models.instruments.base import AbstractSourceMeter, AbstractLuminanceMeter
from models.instruments.keithley2400 import Keithley2400
from models.instruments.keithley2612b import Keithley2612B
from models.instruments.mock.keithley2400_mock import Keithley2400Mock
from models.instruments.mock.keithley2612b_mock import Keithley2612BMock
from models.instruments.bm9 import BM9
from models.instruments.mock.bm9_mock import BM9Mock


def assert_signatures_match(base_class, impl_class):
    """基底クラスの抽象メソッドと実装クラスのメソッドのシグネチャが一致していることを検証する。"""
    # 抽象メソッドをすべて取得
    abstract_methods = []
    for name, member in inspect.getmembers(base_class, predicate=inspect.isfunction):
        if getattr(member, "__isabstractmethod__", False):
            abstract_methods.append(name)

    for method_name in abstract_methods:
        base_method = getattr(base_class, method_name)
        assert hasattr(impl_class, method_name), f"{impl_class.__name__} does not implement {method_name}"
        impl_method = getattr(impl_class, method_name)

        base_sig = inspect.signature(base_method)
        impl_sig = inspect.signature(impl_method)

        # パラメータ数が一致しているか、パラメータの名称が一致しているかを検証
        assert len(base_sig.parameters) == len(impl_sig.parameters), (
            f"Parameter count mismatch in {impl_class.__name__}.{method_name}: "
            f"expected {base_sig}, got {impl_sig}"
        )

        for (base_param_name, base_param), (impl_param_name, impl_param) in zip(
            base_sig.parameters.items(), impl_sig.parameters.items()
        ):
            # パラメータ名が一致していることを検証
            assert base_param_name == impl_param_name, (
                f"Parameter name mismatch in {impl_class.__name__}.{method_name}: "
                f"expected {base_param_name}, got {impl_param_name}"
            )
            # デフォルト値の有無が一致していることを検証
            base_has_default = base_param.default is not inspect.Parameter.empty
            impl_has_default = impl_param.default is not inspect.Parameter.empty
            assert base_has_default == impl_has_default, (
                f"Parameter default value presence mismatch in {impl_class.__name__}.{method_name} for '{base_param_name}'"
            )


def test_sourcemeter_interface_parity():
    """AbstractSourceMeterを実装する各クラスのシグネチャ一致を確認する。"""
    classes_to_test = [Keithley2400, Keithley2612B, Keithley2400Mock, Keithley2612BMock]
    for cls in classes_to_test:
        assert_signatures_match(AbstractSourceMeter, cls)


def test_luminancemeter_interface_parity():
    """AbstractLuminanceMeterを実装する各クラスのシグネチャ一致を確認する。"""
    classes_to_test = [BM9, BM9Mock]
    for cls in classes_to_test:
        assert_signatures_match(AbstractLuminanceMeter, cls)
