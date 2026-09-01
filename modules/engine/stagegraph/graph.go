package stagegraph

import "fmt"

// Graph is a validated, immutable view over Stages: every StageID is unique,
// every DependsOn reference resolves to a known stage, and the dependency
// edges form a DAG (no cycles).
type Graph struct {
	byID map[StageID]Descriptor
	// dependents maps a stage to the stages that directly depend on it
	// (the reverse of Descriptor.DependsOn).
	dependents map[StageID][]StageID
	order      []StageID
}

// NewGraph validates Stages and returns the resulting Graph. It fails on a
// duplicate stage ID, a DependsOn reference to an unknown stage, or a cycle.
func NewGraph() (*Graph, error) {
	byID := make(map[StageID]Descriptor, len(Stages))
	for _, d := range Stages {
		if _, exists := byID[d.ID]; exists {
			return nil, fmt.Errorf("stagegraph: duplicate stage id %q", d.ID)
		}
		byID[d.ID] = d
	}

	for _, d := range Stages {
		for _, dep := range d.DependsOn {
			if _, ok := byID[dep]; !ok {
				return nil, fmt.Errorf("stagegraph: stage %q depends on unknown stage %q", d.ID, dep)
			}
		}
	}

	dependents := make(map[StageID][]StageID, len(Stages))
	inDegree := make(map[StageID]int, len(Stages))
	for _, d := range Stages {
		inDegree[d.ID] = len(d.DependsOn)
		for _, dep := range d.DependsOn {
			dependents[dep] = append(dependents[dep], d.ID)
		}
	}

	order, err := topologicalOrder(byID, dependents, inDegree)
	if err != nil {
		return nil, err
	}

	return &Graph{byID: byID, dependents: dependents, order: order}, nil
}

// topologicalOrder runs Kahn's algorithm. A resulting order shorter than the
// input node count means a cycle exists among the unresolved nodes.
func topologicalOrder(byID map[StageID]Descriptor, dependents map[StageID][]StageID, inDegree map[StageID]int) ([]StageID, error) {
	remaining := make(map[StageID]int, len(inDegree))
	for id, deg := range inDegree {
		remaining[id] = deg
	}

	var ready []StageID
	for _, d := range Stages {
		if remaining[d.ID] == 0 {
			ready = append(ready, d.ID)
		}
	}

	order := make([]StageID, 0, len(byID))
	for len(ready) > 0 {
		next := ready[0]
		ready = ready[1:]
		order = append(order, next)

		for _, dependent := range dependents[next] {
			remaining[dependent]--
			if remaining[dependent] == 0 {
				ready = append(ready, dependent)
			}
		}
	}

	if len(order) != len(byID) {
		stuck := make([]StageID, 0)
		for id, deg := range remaining {
			if deg > 0 {
				stuck = append(stuck, id)
			}
		}
		return nil, fmt.Errorf("stagegraph: cycle detected, stages never satisfied: %v", stuck)
	}

	return order, nil
}

// Descriptor returns the descriptor for id and whether it exists.
func (g *Graph) Descriptor(id StageID) (Descriptor, bool) {
	d, ok := g.byID[id]
	return d, ok
}

// StageIDs returns every stage ID known to the graph, in canon-document order.
func (g *Graph) StageIDs() []StageID {
	ids := make([]StageID, 0, len(Stages))
	for _, d := range Stages {
		ids = append(ids, d.ID)
	}
	return ids
}

// TopologicalOrder returns a dependency-respecting execution order. Its
// existence (no error from NewGraph) already proves the graph is acyclic.
func (g *Graph) TopologicalOrder() []StageID {
	out := make([]StageID, len(g.order))
	copy(out, g.order)
	return out
}

// Ancestors returns the transitive closure of everything id depends on
// (directly or indirectly), not including id itself.
func (g *Graph) Ancestors(id StageID) map[StageID]bool {
	visited := make(map[StageID]bool)
	var visit func(StageID)
	visit = func(cur StageID) {
		d, ok := g.byID[cur]
		if !ok {
			return
		}
		for _, dep := range d.DependsOn {
			if !visited[dep] {
				visited[dep] = true
				visit(dep)
			}
		}
	}
	visit(id)
	return visited
}
