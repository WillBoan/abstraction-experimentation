from arc_lab.program_search.ladders.registry import make_ladder, ladder_paths
for name in sorted(ladder_paths()):
    shape = make_ladder(name).lint()
    f = [x for x in shape.findings if x.code == "primitive-necessity"]
    if f and not f[0].ok:
        print(f"{name}: {f[0].detail.split('not cheap: ',1)[-1][:150]}")
    else:
        print(f"{name}: clean")
