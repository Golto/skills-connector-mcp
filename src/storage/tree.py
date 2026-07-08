def render_file_tree(root_label: str, relative_paths: list[str]) -> str:
    """Render a sorted list of relative file paths as an ASCII directory tree.

    Generic over the source of the paths: works identically for a skill
    directory (from list_skill_files) or a scratch directory (from
    list_scratch_files), since it only operates on path strings.

    Args:
        root_label: Label shown for the root of the tree (e.g. '/skill').
        relative_paths: Sorted relative file paths, using '/' as separator.

    Returns:
        A multi-line string using box-drawing characters, or a single line
        stating the root is empty if relative_paths is empty.
    """
    if not relative_paths:
        return f"{root_label}/ (empty)"

    tree: dict = {}
    for path in relative_paths:
        node = tree
        for part in path.split("/"):
            node = node.setdefault(part, {})

    lines = [f"{root_label}/"]
    _render_node(tree, prefix="", lines=lines)
    return "\n".join(lines)


def _render_node(node: dict, prefix: str, lines: list[str]) -> None:
    """Recursively append rendered lines for one level of the tree.

    Args:
        node: Mapping of child name to its own children mapping (empty dict
            for files).
        prefix: Indentation and connector prefix accumulated so far.
        lines: Output list being appended to in place.
    """
    entries = sorted(node.items())
    for index, (name, children) in enumerate(entries):
        is_last = index == len(entries) - 1
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        suffix = "/" if children else ""
        lines.append(f"{prefix}{connector}{name}{suffix}")
        if children:
            extension = "    " if is_last else "\u2502   "
            _render_node(children, prefix + extension, lines)
