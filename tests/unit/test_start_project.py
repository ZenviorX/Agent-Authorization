from start_project import parser


def test_oauth_starts_by_default() -> None:
    args = parser().parse_args([])

    assert args.with_oauth is True


def test_oauth_can_be_disabled_explicitly() -> None:
    assert parser().parse_args(["--without-oauth"]).with_oauth is False
    assert parser().parse_args(["--no-oauth"]).with_oauth is False


def test_legacy_with_oauth_flag_remains_compatible() -> None:
    args = parser().parse_args(["--with-oauth"])

    assert args.with_oauth is True
