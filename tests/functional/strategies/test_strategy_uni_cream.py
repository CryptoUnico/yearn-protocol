import pytest
import brownie

from brownie import Wei, convert, accounts

from brownie import StrategyCreamUNI, Controller, yVault

MAX_LIMIT = 2 ** 256 - 1

# UNI
TOKEN_CONTRACT = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"
CTOKEN_CONTRACT = "0xe89a6D0509faF730BD707bf868d9A2A744a363C7"

UNI_HOLDER = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"

STRAT_NAME = "StrategyCreamUNI"


@pytest.fixture
def token(Contract):
    yield Contract.from_explorer(TOKEN_CONTRACT)


@pytest.fixture
def cToken(Contract):
    yield Contract.from_explorer(CTOKEN_CONTRACT)


@pytest.fixture
def controller(gov, rewards, Controller):
    controller = gov.deploy(Controller, rewards)
    return controller


@pytest.fixture
def strategy(gov, controller):
    strategy = gov.deploy(StrategyCreamUNI, controller)
    return strategy


@pytest.fixture
def vault(gov, controller, strategy, token):
    # vault setup
    vault = gov.deploy(yVault, token, controller)
    vault.setMin(10000)

    # enable strat
    controller.approveStrategy(token, strategy, {"from": gov})
    controller.setStrategy(token, strategy, {"from": gov})
    controller.setVault(token, vault)

    return vault


def test_deployment(strategy, vault, token, gov, controller):
    # check strat values
    assert strategy.governance() == gov
    assert strategy.controller() == controller
    assert strategy.getName() == STRAT_NAME

    # check vault values
    assert vault.governance() == gov
    assert vault.controller() == controller
    assert vault.token() == token
    assert vault.name() == "yearn " + token.name()
    assert vault.symbol() == "y" + token.symbol()
    assert vault.decimals() == token.decimals()


def test_deposit(strategy, vault, token, cToken, gov):
    # setup accounts
    uni_holder = accounts.at(UNI_HOLDER, force=True)
    user = accounts[7]
    # fund user wallet with UNI
    token.approve(uni_holder, Wei("1000 ether"), {"from": uni_holder})
    token.transferFrom(uni_holder, user, Wei("1000 ether"), {"from": uni_holder})
    token.approve(vault, Wei("1000 ether"), {"from": user})

    # execute and expectations
    vault.depositAll({"from": user})
    assert vault.balanceOf(user) == Wei("1000 ether")
    assert cToken.balanceOf(strategy) == 0
    vault.earn({"from": gov})
    assert strategy.balanceC() == cToken.balanceOf(strategy)
    # strategy.harvest({"from": gov})
    assert vault.getPricePerFullShare() > 1
    assert vault.balanceOf(user) >= Wei("1000 ether")


def test_vault_withdraw(strategy, vault, token, cToken, gov):
    # setup accounts and expectations
    uni_holder = accounts.at(UNI_HOLDER, force=True)
    user = accounts[8]
    # fund user wallet with UNI
    token.approve(uni_holder, Wei("100 ether"), {"from": uni_holder})
    token.transferFrom(uni_holder, user, Wei("100 ether"), {"from": uni_holder})
    assert token.balanceOf(user) == Wei("100 ether")
    token.approve(vault, Wei("100 ether"), {"from": user})

    # execute
    vault.deposit(Wei("100 ether"), {"from": user})
    vault.withdraw(Wei("100 ether"), {"from": user})

    # expectations
    assert token.balanceOf(user) == Wei("100 ether")


def test_vault_withdraw_with_fee(strategy, vault, token, cToken, gov, rewards):
    # setup accounts and expectations
    uni_holder = accounts.at(UNI_HOLDER, force=True)
    user = accounts[9]
    # fund user wallet with UNI
    token.approve(uni_holder, Wei("105 ether"), {"from": uni_holder})
    token.transferFrom(uni_holder, user, Wei("105 ether"), {"from": uni_holder})
    token.approve(vault, Wei("105 ether"), {"from": user})

    # execute
    vault.deposit(Wei("105 ether"), {"from": user})
    vault.earn({"from": gov})
    vault.withdraw(Wei("100 ether"), {"from": user})

    # expectations
    assert token.balanceOf(user) >= Wei("99.5 ether")
    assert token.balanceOf(rewards) >= Wei("0.5 ether")


def test_vault_withdraw_all(strategy, vault, token, cToken, gov, rewards):
    # setup accounts and expectations
    uni_holder = accounts.at(UNI_HOLDER, force=True)
    user = accounts[8]
    user2 = accounts[9]
    # fund user wallet with UNI
    token.approve(uni_holder, Wei("210 ether"), {"from": uni_holder})
    token.transferFrom(uni_holder, user, Wei("105 ether"), {"from": uni_holder})
    token.transferFrom(uni_holder, user2, Wei("105 ether"), {"from": uni_holder})
    token.approve(vault, Wei("105 ether"), {"from": user})
    token.approve(vault, Wei("105 ether"), {"from": user2})

    # execute
    vault.deposit(Wei("105 ether"), {"from": user})
    vault.deposit(Wei("105 ether"), {"from": user2})
    vault.earn({"from": gov})
    vault.withdrawAll({"from": user})

    # expectations
    assert token.balanceOf(user) >= Wei("99.5 ether")
    assert token.balanceOf(rewards) >= Wei("0.5 ether")


def test_strategy_withdraw_all(
    strategy, controller, vault, token, cToken, gov, rewards
):
    # setup accounts and expectations
    uni_holder = accounts.at(UNI_HOLDER, force=True)
    user = accounts[8]
    # fund user wallet with UNI
    token.approve(uni_holder, Wei("105 ether"), {"from": uni_holder})
    token.transferFrom(uni_holder, user, Wei("105 ether"), {"from": uni_holder})
    token.approve(vault, Wei("105 ether"), {"from": user})

    # execute
    vault.deposit(Wei("105 ether"), {"from": user})
    vault.earn({"from": gov})
    assert token.balanceOf(vault) == 0
    controller.withdrawAll(token.address, {"from": gov})

    # expectations
    assert cToken.balanceOf(strategy) == 0
    assert token.balanceOf(vault) >= Wei("105 ether")


def max_approve(token, address, from_account):
    token.approve(address, MAX_LIMIT, {"from": from_account})