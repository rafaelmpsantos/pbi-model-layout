import React, { useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.3.1?dev";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client?dev&deps=react@18.3.1";
import { toPng } from "https://esm.sh/html-to-image@1.11.11";
import ReactFlow, {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  MiniMap,
  Panel,
  Position,
  ReactFlowProvider,
  getSmoothStepPath,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "https://esm.sh/reactflow@11.11.4?dev&deps=react@18.3.1,react-dom@18.3.1";

const HEADER_HEIGHT = 52;
const ROW_HEIGHT = 24;

const ROLE_STYLES = {
  fact: { header: "#2b579a", border: "#3b82f6", badge: "FACT", accent: "#dbeafe" },
  dimension: { header: "#74489d", border: "#9d4edd", badge: "DIM", accent: "#f3e8ff" },
  snowflake: { header: "#2d7a4f", border: "#16a34a", badge: "SNOW", accent: "#dcfce7" },
  other: { header: "#4b5563", border: "#64748b", badge: "OTHER", accent: "#e2e8f0" },
};

const RELATIONSHIP_ICON = "\u25C6";
const COLUMN_ICON = "\u25E6";
const DEFAULT_FACT_PREFIXES = ["fct_", "fact_"];
const DEFAULT_DIM_PREFIXES = ["dim_", "d_"];

function parsePrefixList(raw) {
  return (raw || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function matchesPrefix(name, prefixes) {
  const normalizedName = (name || "").toLowerCase();
  return prefixes.some((prefix) => normalizedName.startsWith(prefix));
}

function placeRow(nodes, centerX, y, gap = 84) {
  if (!nodes.length) {
    return {};
  }
  const totalWidth = nodes.reduce((sum, node) => sum + (node.data?.width || 260), 0) + gap * (nodes.length - 1);
  let cursorX = centerX - totalWidth / 2;
  const positions = {};
  nodes.forEach((node) => {
    positions[node.id] = { x: cursorX, y };
    cursorX += (node.data?.width || 260) + gap;
  });
  return positions;
}

function snapshotNodePositions(nodeList) {
  const positions = {};
  (nodeList || []).forEach((node) => {
    positions[node.id] = {
      x: node.position?.x ?? 0,
      y: node.position?.y ?? 0,
    };
  });
  return positions;
}

function mergeNodePositions(nodeList, defaultPositions, savedPositions) {
  return (nodeList || []).map((node) => ({
    ...node,
    position: savedPositions?.[node.id] || defaultPositions.get(node.id) || node.position,
  }));
}

function buildColumnHandle(prefix, columnName) {
  return `${prefix}::${columnName || "__default__"}`;
}

function resolveEdgeHandles(edge, sourceNode, targetNode) {
  if (!sourceNode || !targetNode) {
    return {
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
    };
  }

  const sourceCenterX = (sourceNode.position?.x || 0) + ((sourceNode.data?.width || 260) / 2);
  const targetCenterX = (targetNode.position?.x || 0) + ((targetNode.data?.width || 260) / 2);
  const sourceOnLeft = sourceCenterX <= targetCenterX;

  return {
    sourceHandle: buildColumnHandle(sourceOnLeft ? "right-source" : "left-source", edge.data?.fromColumn),
    targetHandle: buildColumnHandle(sourceOnLeft ? "left-target" : "right-target", edge.data?.toColumn),
  };
}

function isLocalDateTableName(name) {
  const normalized = (name || "").toLowerCase();
  return normalized.includes("localdate table") || normalized.includes("localdatetable");
}

function buildFilteredLayout(baseNodes, baseEdges, selectedTables, visibleTableIds) {
  if (!selectedTables.length) {
    return new Map((baseNodes || []).map((node) => [node.id, node.position]));
  }

  const visibleNodes = (baseNodes || []).filter((node) => visibleTableIds.has(node.id));
  const byId = new Map(visibleNodes.map((node) => [node.id, node]));
  const selectedSet = new Set(selectedTables);
  const adjacency = new Map();

  visibleNodes.forEach((node) => adjacency.set(node.id, new Set()));
  (baseEdges || []).forEach((edge) => {
    if (!visibleTableIds.has(edge.source) || !visibleTableIds.has(edge.target)) {
      return;
    }
    adjacency.get(edge.source)?.add(edge.target);
    adjacency.get(edge.target)?.add(edge.source);
  });

  const selectedNodes = selectedTables
    .map((id) => byId.get(id))
    .filter(Boolean)
    .sort((a, b) => a.position.x - b.position.x);
  const sharedNodes = [];
  const topByOwner = new Map();
  const bottomByOwner = new Map();
  const looseNodes = [];

  selectedNodes.forEach((node) => {
    topByOwner.set(node.id, []);
    bottomByOwner.set(node.id, []);
  });

  visibleNodes
    .filter((node) => !selectedSet.has(node.id))
    .forEach((node) => {
      const linkedSelected = [...(adjacency.get(node.id) || [])].filter((id) => selectedSet.has(id));
      if (!linkedSelected.length) {
        looseNodes.push(node);
        return;
      }
      if (linkedSelected.length > 1) {
        sharedNodes.push(node);
        return;
      }

      const ownerId = linkedSelected[0];
      const bucket =
        node.data?.role === "dimension" || node.data?.role === "snowflake"
          ? topByOwner
          : bottomByOwner;
      bucket.get(ownerId)?.push(node);
    });

  const positions = new Map();
  const selectedMaxHeight = Math.max(...selectedNodes.map((node) => node.data?.height || 180), 180);
  const sharedMaxHeight = sharedNodes.length
    ? Math.max(...sharedNodes.map((node) => node.data?.height || 180), 180)
    : 0;

  Object.entries(placeRow(selectedNodes, 0, 0, 130)).forEach(([id, position]) => {
    positions.set(id, position);
  });

  const selectedCenters = new Map(
    selectedNodes.map((node) => {
      const pos = positions.get(node.id) || { x: 0, y: 0 };
      return [node.id, pos.x + (node.data?.width || 260) / 2];
    })
  );

  if (sharedNodes.length) {
    Object.entries(
      placeRow(
        sharedNodes.sort((a, b) => a.position.x - b.position.x),
        0,
        -(sharedMaxHeight + 110),
        96
      )
    ).forEach(([id, position]) => {
      positions.set(id, position);
    });
  }

  selectedNodes.forEach((node) => {
    const centerX = selectedCenters.get(node.id) || 0;
    const ownerTop = (topByOwner.get(node.id) || []).sort((a, b) => a.position.x - b.position.x);
    const ownerBottom = (bottomByOwner.get(node.id) || []).sort((a, b) => a.position.x - b.position.x);
    const topHeight = ownerTop.length ? Math.max(...ownerTop.map((item) => item.data?.height || 180), 180) : 0;
    const topY = -(topHeight + selectedMaxHeight + 150);
    const bottomY = selectedMaxHeight + 150;

    Object.entries(placeRow(ownerTop, centerX, topY, 82)).forEach(([id, position]) => {
      positions.set(id, position);
    });
    Object.entries(placeRow(ownerBottom, centerX, bottomY, 82)).forEach(([id, position]) => {
      positions.set(id, position);
    });
  });

  if (looseNodes.length) {
    const bottomMostY = [...positions.entries()].reduce((maxY, [id, position]) => {
      const node = byId.get(id);
      return Math.max(maxY, position.y + (node?.data?.height || 180));
    }, 0);
    Object.entries(
      placeRow(
        looseNodes.sort((a, b) => a.position.x - b.position.x),
        0,
        bottomMostY + 120,
        88
      )
    ).forEach(([id, position]) => {
      positions.set(id, position);
    });
  }

  return positions;
}

function TableNode({ data, selected }) {
  const palette = ROLE_STYLES[data.role] || ROLE_STYLES.other;
  const columns = data.columns || [];
  const width = data.width || 260;

  return React.createElement(
    "div",
    {
      className: `rf-node${selected ? " selected" : ""}${data.isDimmed ? " dimmed" : ""}`,
      style: { width, borderColor: palette.border },
    },
    React.createElement(
      "div",
      {
        className: "rf-node-header",
        style: { background: palette.header },
      },
      React.createElement(
        "div",
        { className: "rf-node-header-main" },
        React.createElement("span", { className: "rf-node-header-title" }, data.label),
        React.createElement(
          "span",
          {
            className: "rf-node-header-badge",
            style: { background: palette.accent, color: palette.header },
          },
          palette.badge
        )
      ),
      React.createElement(
        "div",
        { className: "rf-node-header-subtitle" },
        `${columns.length} column${columns.length === 1 ? "" : "s"}`
      )
    ),
    React.createElement(
      "div",
      { className: "rf-node-body" },
      columns.length
        ? columns.map((column, index) =>
            React.createElement(
              "div",
              {
                key: `${data.label}-${column.name}-${index}`,
                className: `rf-node-row${column.isRelationship ? " relationship" : ""}${column.isActive ? " active" : ""}`,
              },
              React.createElement(Handle, {
                id: `left-target::${column.name || "__default__"}`,
                type: "target",
                position: Position.Left,
                className: "rf-handle",
                style: {
                  top: "50%",
                  left: -6,
                  transform: "translateY(-50%)",
                },
              }),
              React.createElement(Handle, {
                id: `left-source::${column.name || "__default__"}`,
                type: "source",
                position: Position.Left,
                className: "rf-handle",
                style: {
                  top: "50%",
                  left: -6,
                  transform: "translateY(-50%)",
                  opacity: 0,
                },
              }),
              React.createElement(Handle, {
                id: `right-source::${column.name || "__default__"}`,
                type: "source",
                position: Position.Right,
                className: "rf-handle",
                style: {
                  top: "50%",
                  right: -6,
                  transform: "translateY(-50%)",
                },
              }),
              React.createElement(Handle, {
                id: `right-target::${column.name || "__default__"}`,
                type: "target",
                position: Position.Right,
                className: "rf-handle",
                style: {
                  top: "50%",
                  right: -6,
                  transform: "translateY(-50%)",
                  opacity: 0,
                },
              }),
              React.createElement(
                "span",
                { className: "rf-node-row-icon" },
                column.isRelationship ? RELATIONSHIP_ICON : COLUMN_ICON
              ),
              React.createElement("span", { className: "rf-node-row-name" }, column.name)
            )
          )
        : React.createElement(
            "div",
            { className: "rf-node-empty" },
            "-"
          )
    )
  );
}

function RelationshipEdge(props) {
  const {
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style,
    markerEnd,
    selected,
    data,
  } = props;

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 20,
    offset: 28,
  });

  const edgeStyle = {
    stroke: selected ? "#2563eb" : data?.isDimmed ? "rgba(139,152,167,0.28)" : "#8b98a7",
    strokeWidth: selected ? 3 : 2,
    ...style,
  };

  const directionText = data?.direction === "both" ? "↔ Both" : data?.direction === "single" ? "→ Single" : null;
  const midSourceX = sourceX + (targetX - sourceX) * 0.18;
  const midTargetX = targetX - (targetX - sourceX) * 0.18;

  const hoverProps = {
    onMouseEnter: data?.onHoverStart,
    onMouseMove: data?.onHoverMove,
    onMouseLeave: data?.onHoverEnd,
  };

  return React.createElement(
    React.Fragment,
    null,
    React.createElement(BaseEdge, { id, path: edgePath, style: edgeStyle, markerEnd, interactionWidth: 24 }),
    React.createElement(
      EdgeLabelRenderer,
      null,
      React.createElement(
        "div",
        {
          className: `rf-edge-cardinality${data?.isDimmed ? " dimmed" : ""}`,
          style: { left: `${midSourceX}px`, top: `${sourceY}px` },
          ...hoverProps,
        },
        data?.fromCardinality || "?"
      ),
      React.createElement(
        "div",
        {
          className: `rf-edge-cardinality${data?.isDimmed ? " dimmed" : ""}`,
          style: { left: `${midTargetX}px`, top: `${targetY}px` },
          ...hoverProps,
        },
        data?.toCardinality || "?"
      ),
      React.createElement(
        "div",
        {
          className: `rf-edge-label${data?.isDimmed ? " dimmed" : ""}`,
          style: { left: `${labelX}px`, top: `${labelY}px` },
          ...hoverProps,
        },
        React.createElement(
          "div",
          { className: `rf-edge-pill${selected ? " selected" : ""}` },
          React.createElement("strong", null, data?.cardinalityLabel || "?"),
          directionText ? React.createElement("span", null, directionText) : null,
          React.createElement(
            "span",
            null,
            data?.fromColumn && data?.toColumn
              ? `${data.fromColumn} → ${data.toColumn}`
              : data?.directionLabel || "?"
          )
        )
      )
    )
  );
}

function FlowDiagram({ graph, texts }) {
  const shellRef = useRef(null);
  const filterPanelRef = useRef(null);
  const rolePanelRef = useRef(null);
  const isRestoringViewportRef = useRef(false);
  const [nodes, setNodes, baseOnNodesChange] = useNodesState(graph.nodes || []);
  const [edges, , onEdgesChange] = useEdgesState(graph.edges || []);
  const [selectedTables, setSelectedTables] = useState([]);
  const [customViews, setCustomViews] = useState([]);
  const [activeViewId, setActiveViewId] = useState("all");
  const [hoveredEdgeId, setHoveredEdgeId] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [search, setSearch] = useState("");
  const [roleSearch, setRoleSearch] = useState("");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [pendingFitIds, setPendingFitIds] = useState(null);
  const [pendingViewport, setPendingViewport] = useState(null);
  const [showLocalDateTables, setShowLocalDateTables] = useState(true);
  const [factPrefixesText, setFactPrefixesText] = useState(DEFAULT_FACT_PREFIXES.join(", "));
  const [dimPrefixesText, setDimPrefixesText] = useState(DEFAULT_DIM_PREFIXES.join(", "));
  const [manualRoles, setManualRoles] = useState({});
  const [savedLayouts, setSavedLayouts] = useState({});
  const reactFlow = useReactFlow();

  const hoveredEdge = useMemo(
    () => (graph.edges || []).find((edge) => edge.id === hoveredEdgeId) || null,
    [graph.edges, hoveredEdgeId]
  );

  const baseNodes = useMemo(() => graph.nodes || [], [graph.nodes]);

  const availableNodes = useMemo(
    () =>
      showLocalDateTables
        ? baseNodes
        : baseNodes.filter((node) => !isLocalDateTableName(node.id)),
    [baseNodes, showLocalDateTables]
  );

  const allTableNames = useMemo(
    () => availableNodes.map((node) => node.id).sort((a, b) => a.localeCompare(b)),
    [availableNodes]
  );

  const factPrefixes = useMemo(() => parsePrefixList(factPrefixesText), [factPrefixesText]);
  const dimPrefixes = useMemo(() => parsePrefixList(dimPrefixesText), [dimPrefixesText]);

  const effectiveRoles = useMemo(() => {
    const map = new Map();
    baseNodes.forEach((node) => {
      const manualRole = manualRoles[node.id];
      let role = node.data?.role || "other";
      if (manualRole && manualRole !== "auto") {
        role = manualRole;
      } else if (matchesPrefix(node.id, factPrefixes)) {
        role = "fact";
      } else if (matchesPrefix(node.id, dimPrefixes)) {
        role = node.data?.role === "snowflake" ? "snowflake" : "dimension";
      }
      map.set(node.id, role);
    });
    return map;
  }, [baseNodes, dimPrefixes, factPrefixes, manualRoles]);

  const layoutNodes = useMemo(
    () =>
      availableNodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          role: effectiveRoles.get(node.id) || node.data?.role || "other",
        },
      })),
    [availableNodes, effectiveRoles]
  );

  const factViews = useMemo(
    () =>
      layoutNodes
        .filter((node) => node.data?.role === "fact")
        .sort((a, b) => a.id.localeCompare(b.id))
        .map((node) => ({ id: `fact:${node.id}`, label: node.id, tables: [node.id], kind: "fact" })),
    [layoutNodes]
  );

  const customViewTabs = useMemo(
    () => customViews.map((view) => ({ ...view, kind: "custom" })),
    [customViews]
  );

  const visibleTableIds = useMemo(() => {
    const availableTableIds = new Set(allTableNames);
    if (!selectedTables.length) {
      return availableTableIds;
    }

    const visible = new Set(selectedTables.filter((name) => availableTableIds.has(name)));
    (graph.edges || []).forEach((edge) => {
      if (selectedTables.includes(edge.source) || selectedTables.includes(edge.target)) {
        if (availableTableIds.has(edge.source)) {
          visible.add(edge.source);
        }
        if (availableTableIds.has(edge.target)) {
          visible.add(edge.target);
        }
      }
    });
    return visible;
  }, [allTableNames, graph.edges, selectedTables]);

  useEffect(() => {
    setSelectedTables((current) => current.filter((name) => allTableNames.includes(name)));
  }, [allTableNames]);

  const activeLayoutKey = useMemo(() => {
    if (activeViewId === "selection") {
      const selectedKey = [...selectedTables].sort((a, b) => a.localeCompare(b)).join("|");
      return selectedKey ? `selection:${selectedKey}` : "all";
    }
    return activeViewId || "all";
  }, [activeViewId, selectedTables]);

  const activeTables = useMemo(() => {
    if (!hoveredEdge) {
      return null;
    }
    return new Set([hoveredEdge.source, hoveredEdge.target]);
  }, [hoveredEdge]);

  const roleOptions = useMemo(
    () => [
      { value: "auto", label: texts.role_auto || "Auto" },
      { value: "fact", label: texts.role_fact || "Fact" },
      { value: "dimension", label: texts.role_dimension || "Dimension" },
      { value: "snowflake", label: texts.role_snowflake || "Snowflake" },
      { value: "other", label: texts.role_other || "Other" },
    ],
    [texts]
  );

  const roleFilteredNames = useMemo(() => {
    const query = roleSearch.trim().toLowerCase();
    if (!query) {
      return allTableNames;
    }
    return allTableNames.filter((name) => name.toLowerCase().includes(query));
  }, [allTableNames, roleSearch]);

  const startEdgeHover = (edge, event) => {
    setHoveredEdgeId(edge.id);
    setTooltip({ x: event.clientX + 16, y: event.clientY + 16, edge });
  };

  const moveEdgeHover = (edge, event) => {
    setTooltip({ x: event.clientX + 16, y: event.clientY + 16, edge });
  };

  const endEdgeHover = () => {
    setHoveredEdgeId(null);
    setTooltip(null);
  };

  const flowNodes = useMemo(
    () =>
      nodes.map((node) => {
        const isVisible = visibleTableIds.has(node.id);
        const isEdgeTable = activeTables ? activeTables.has(node.id) : false;
        const role = effectiveRoles.get(node.id) || node.data?.role || "other";
        return {
          ...node,
          hidden: !isVisible,
          selected: Boolean(hoveredEdge && isEdgeTable),
          data: {
            ...node.data,
            role,
            isDimmed: Boolean(hoveredEdge && !isEdgeTable),
            columns: (node.data.columns || []).map((column) => ({
              ...column,
              isActive:
                Boolean(hoveredEdge) &&
                ((node.id === hoveredEdge?.source && column.name === hoveredEdge?.data?.fromColumn) ||
                  (node.id === hoveredEdge?.target && column.name === hoveredEdge?.data?.toColumn)),
            })),
          },
        };
      }),
    [activeTables, effectiveRoles, hoveredEdge, nodes, visibleTableIds]
  );

  const flowEdges = useMemo(
    () => {
      const nodesById = new Map(nodes.map((node) => [node.id, node]));
      return edges.map((edge) => {
        const sourceNode = nodesById.get(edge.source);
        const targetNode = nodesById.get(edge.target);
        const handles = resolveEdgeHandles(edge, sourceNode, targetNode);
        return {
          ...edge,
          ...handles,
          hidden: !(visibleTableIds.has(edge.source) && visibleTableIds.has(edge.target)),
          selected: edge.id === hoveredEdgeId,
          data: {
            ...edge.data,
            isDimmed: Boolean(hoveredEdgeId && edge.id !== hoveredEdgeId),
            onHoverStart: (event) => startEdgeHover(edge, event),
            onHoverMove: (event) => moveEdgeHover(edge, event),
            onHoverEnd: endEdgeHover,
          },
        };
      });
    },
    [edges, hoveredEdgeId, nodes, visibleTableIds]
  );

  const filteredTableNames = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return allTableNames;
    }
    return allTableNames.filter((name) => name.toLowerCase().includes(query));
  }, [allTableNames, search]);

  const fitDiagram = (duration = 250, tableIds = null) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const targetIds = tableIds && tableIds.length ? new Set(tableIds) : null;
        const targetNodes = targetIds
          ? reactFlow.getNodes().filter((node) => targetIds.has(node.id))
          : undefined;
        reactFlow.fitView({
          padding: 0.22,
          duration,
          includeHiddenNodes: false,
          nodes: targetNodes && targetNodes.length ? targetNodes : undefined,
        });
      });
    });
  };

  const saveCurrentLayout = (nodeList = reactFlow.getNodes(), viewport = reactFlow.getViewport()) => {
    setSavedLayouts((current) => ({
      ...current,
      [activeLayoutKey]: {
        positions: snapshotNodePositions(nodeList),
        viewport,
      },
    }));
  };

  const onNodesChange = (changes) => {
    baseOnNodesChange(changes);
  };

  const applyViewSelection = (viewId, tables) => {
    setActiveViewId(viewId);
    setSelectedTables([...tables]);
    setHoveredEdgeId(null);
    setTooltip(null);
    setSearch("");
  };

  const createCustomView = () => {
    const tables = [...selectedTables].sort((a, b) => a.localeCompare(b));
    if (!tables.length) {
      return;
    }
    const suggestedName = `${texts.view_new_default || "Custom view"} ${customViews.length + 1}`;
    const name = window.prompt(texts.view_new_prompt || "Name for the new view:", suggestedName);
    if (!name) {
      return;
    }
    const trimmedName = name.trim();
    if (!trimmedName) {
      return;
    }
    const view = {
      id: `custom:${Date.now()}`,
      label: trimmedName,
      tables,
    };
    setCustomViews((current) => [...current, view]);
    setActiveViewId(view.id);
  };

  const removeCustomView = (viewId) => {
    setCustomViews((current) => current.filter((view) => view.id !== viewId));
    if (activeViewId === viewId) {
      applyViewSelection("all", []);
    }
  };

  const toggleTable = (tableName) => {
    setActiveViewId("selection");
    setSelectedTables((current) =>
      current.includes(tableName)
        ? current.filter((name) => name !== tableName)
        : [...current, tableName]
    );
  };

  const updateManualRole = (tableName, value) => {
    setManualRoles((current) => {
      const next = { ...current };
      if (!value || value === "auto") {
        delete next[tableName];
      } else {
        next[tableName] = value;
      }
      return next;
    });
  };

  const resetPrefixes = () => {
    setFactPrefixesText(DEFAULT_FACT_PREFIXES.join(", "));
    setDimPrefixesText(DEFAULT_DIM_PREFIXES.join(", "));
    setManualRoles({});
  };

  useEffect(() => {
    fitDiagram(250);
  }, [reactFlow]);

  useEffect(() => {
    const nextPositions = buildFilteredLayout(layoutNodes, graph.edges || [], selectedTables, visibleTableIds);
    const savedLayout = savedLayouts[activeLayoutKey];
    setNodes(mergeNodePositions(layoutNodes, nextPositions, savedLayout?.positions));
    if (savedLayout?.viewport) {
      setPendingViewport(savedLayout.viewport);
      setPendingFitIds(null);
      return;
    }
    setPendingViewport(null);
    setPendingFitIds([...visibleTableIds]);
  }, [activeLayoutKey, graph.edges, layoutNodes, selectedTables, setNodes, visibleTableIds]);

  useEffect(() => {
    if (!pendingFitIds) {
      return;
    }
    fitDiagram(selectedTables.length ? 220 : 180, pendingFitIds);
    setPendingFitIds(null);
  }, [pendingFitIds, reactFlow, selectedTables]);

  useEffect(() => {
    if (!pendingViewport) {
      return;
    }
    requestAnimationFrame(() => {
      isRestoringViewportRef.current = true;
      reactFlow.setViewport(pendingViewport, { duration: 180 });
      window.setTimeout(() => {
        isRestoringViewportRef.current = false;
      }, 220);
      setPendingViewport(null);
    });
  }, [pendingViewport, reactFlow]);

  useEffect(() => {
    if (!selectedTables.length && activeViewId === "selection") {
      setActiveViewId("all");
    }
  }, [activeViewId, selectedTables]);

  useEffect(() => {
    if (activeViewId.startsWith("fact:") && !factViews.some((view) => view.id === activeViewId)) {
      applyViewSelection("all", []);
    }
  }, [activeViewId, factViews]);

  useEffect(() => {
    const onFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
      fitDiagram(200, [...visibleTableIds]);
    };

    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, [reactFlow, visibleTableIds]);

  const selectedSummary = selectedTables.length
    ? texts.filter_selected_count.replace("{count}", selectedTables.length)
    : texts.filter_selected_none;

  const toggleFullscreen = async () => {
    if (!shellRef.current || !document.fullscreenEnabled) {
      return;
    }
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await shellRef.current.requestFullscreen();
    }
  };

  const tabs = [
    { id: "all", label: texts.view_all_tables || "All tables", tables: [], kind: "all" },
    ...factViews,
    ...customViewTabs,
  ];

  if (activeViewId === "selection" && selectedTables.length) {
    tabs.push({
      id: "selection",
      label: texts.view_current_selection || "Current selection",
      tables: selectedTables,
      kind: "selection",
    });
  }

  const exportDiagramPng = async () => {
    const canvasElement = shellRef.current?.querySelector(".rf-canvas");
    if (!canvasElement) {
      window.alert(texts.export_failed || "Could not export the diagram as PNG.");
      return;
    }

    const controls = [...canvasElement.querySelectorAll(".react-flow__panel, .react-flow__controls, .react-flow__minimap")];
    const previousVisibility = controls.map((element) => element.style.visibility);

    try {
      controls.forEach((element) => {
        element.style.visibility = "hidden";
      });

      const dataUrl = await toPng(canvasElement, {
        cacheBust: true,
        pixelRatio: 2,
        backgroundColor: "#f8fafc",
      });
      const activeTab = tabs.find((tab) => tab.id === activeViewId);
      const safeName = (activeTab?.label || "diagram")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "diagram";
      const link = document.createElement("a");
      link.download = `model-diagram-${safeName}.png`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      window.alert(texts.export_failed || "Could not export the diagram as PNG.");
    } finally {
      controls.forEach((element, index) => {
        element.style.visibility = previousVisibility[index] || "";
      });
    }
  };

  const resetLayoutView = () => {
    const defaultPositions = buildFilteredLayout(layoutNodes, graph.edges || [], selectedTables, visibleTableIds);
    setSavedLayouts((current) => {
      const next = { ...current };
      delete next[activeLayoutKey];
      return next;
    });
    setNodes(mergeNodePositions(layoutNodes, defaultPositions));
    setHoveredEdgeId(null);
    setTooltip(null);
    setSearch("");
    setRoleSearch("");
    setPendingViewport(null);
    setPendingFitIds([...visibleTableIds]);
  };

  const closeFilterPanel = () => {
    if (filterPanelRef.current) {
      filterPanelRef.current.open = false;
    }
  };

  const closeRolePanel = () => {
    if (rolePanelRef.current) {
      rolePanelRef.current.open = false;
    }
  };

  return React.createElement(
    "div",
    { className: "rf-shell", ref: shellRef },
    React.createElement(
      "div",
      { className: "rf-toolbar" },
      React.createElement(
        "button",
        { type: "button", onClick: exportDiagramPng },
        texts.export_png || "Export PNG"
      ),
      React.createElement(
        "button",
        { type: "button", onClick: resetLayoutView },
        texts.reset_view
      ),
      React.createElement(
        "button",
        { type: "button", className: "primary", onClick: toggleFullscreen },
        isFullscreen ? texts.exit_fullscreen : texts.fullscreen
      ),
      React.createElement("span", { className: "rf-hint" }, texts.diagram_hint)
    ),
    React.createElement(
      "div",
      { className: "rf-viewbar" },
      tabs.map((tab) =>
        React.createElement(
          "button",
          {
            key: tab.id,
            type: "button",
            className: `rf-viewtab ${tab.kind}${activeViewId === tab.id ? " active" : ""}`,
            onClick: () => applyViewSelection(tab.id, tab.tables),
          },
          React.createElement("span", null, tab.label),
          tab.kind === "custom"
            ? React.createElement(
                "span",
                {
                  className: "rf-viewtab-remove",
                  title: texts.view_remove || "Remove view",
                  onClick: (event) => {
                    event.stopPropagation();
                    removeCustomView(tab.id);
                  },
                },
                "×"
              )
            : null
        )
      ),
      React.createElement(
        "div",
        { className: "rf-view-actions" },
        React.createElement(
          "button",
          {
            type: "button",
            onClick: createCustomView,
            disabled: !selectedTables.length,
            title: selectedTables.length ? "" : (texts.view_save_disabled || "Select one or more tables to save a custom view"),
          },
          texts.view_save_current || "Save current view"
        )
      )
    ),
    React.createElement(
      "div",
      { className: "rf-canvas" },
      tooltip
        ? React.createElement(
            "div",
            {
              className: "rf-tooltip",
              style: { left: `${tooltip.x}px`, top: `${tooltip.y}px` },
            },
            React.createElement("strong", null, tooltip.edge.data?.cardinalityLabel || "?"),
            React.createElement("span", null, `${texts.relationship_from_label}: ${tooltip.edge.source}`),
            React.createElement("span", null, `${texts.relationship_to_label}: ${tooltip.edge.target}`),
            React.createElement("span", null, `${texts.relationship_columns_label}: ${tooltip.edge.data?.fromColumn || "-"} → ${tooltip.edge.data?.toColumn || "-"}`),
            React.createElement("span", null, `${texts.relationship_filter_label}: ${tooltip.edge.data?.direction === "both" ? "Both" : tooltip.edge.data?.direction === "single" ? (tooltip.edge.data?.directionLabel || "Single") : (tooltip.edge.data?.directionLabel || "?")}`)
          )
        : null,
      React.createElement(
        ReactFlow,
        {
          nodes: flowNodes,
          edges: flowEdges,
          nodeTypes: { tableNode: TableNode },
          edgeTypes: { relationshipEdge: RelationshipEdge },
          onNodesChange,
          onEdgesChange,
          onNodeDragStop: () => saveCurrentLayout(reactFlow.getNodes()),
          onNodeDrag: () => setPendingViewport(null),
          onMoveEnd: (event, viewport) => {
            if (isRestoringViewportRef.current) {
              return;
            }
            saveCurrentLayout(reactFlow.getNodes(), viewport);
          },
          onPaneClick: () => {
            endEdgeHover();
            closeFilterPanel();
            closeRolePanel();
          },
          onPaneMouseLeave: endEdgeHover,
          onEdgeMouseEnter: (event, edge) => startEdgeHover(edge, event),
          onEdgeMouseMove: (event, edge) => moveEdgeHover(edge, event),
          onEdgeMouseLeave: endEdgeHover,
          defaultEdgeOptions: {
            markerEnd: {
              type: MarkerType.ArrowClosed,
              width: 16,
              height: 16,
              color: "#8b98a7",
            },
          },
          fitView: true,
          minZoom: 0.2,
          maxZoom: 1.8,
          nodesDraggable: true,
          proOptions: { hideAttribution: true },
        },
        React.createElement(Background, { gap: 18, color: "#d7e0ea" }),
        React.createElement(Controls, null),
        React.createElement(MiniMap, {
          pannable: true,
          zoomable: true,
          nodeColor: (node) => ROLE_STYLES[node.data?.role || "other"].header,
          maskColor: "rgba(241, 245, 249, 0.78)",
        }),
        React.createElement(
          Panel,
          { position: "bottom-center" },
          React.createElement(
            "div",
            { className: "rf-legend" },
            Object.entries(ROLE_STYLES).map(([role, palette]) =>
              React.createElement(
                "div",
                { key: role, className: "rf-legend-item" },
                React.createElement("span", {
                  className: "rf-legend-swatch",
                  style: { background: palette.header },
                }),
                React.createElement("span", null, palette.badge)
              )
            )
          )
        ),
        React.createElement(
          Panel,
          { position: "top-left" },
          React.createElement(
            "details",
            { className: "rf-panel", ref: filterPanelRef },
            React.createElement(
              "summary",
              null,
              React.createElement(
                "div",
                { className: "rf-panel-title" },
                React.createElement("strong", null, texts.table_filter_toggle),
                React.createElement("span", null, selectedSummary)
              ),
              React.createElement("span", { className: "rf-panel-caret" }, "▾")
            ),
            React.createElement(
              "div",
              { className: "rf-panel-body" },
              selectedTables.length
                ? React.createElement(
                    "div",
                    { className: "rf-chip-list" },
                    selectedTables.slice(0, 8).map((name) =>
                      React.createElement("span", { key: name, className: "rf-chip" }, name)
                    ),
                    selectedTables.length > 8
                      ? React.createElement("span", { className: "rf-chip" }, `+${selectedTables.length - 8}`)
                      : null
                  )
                : null,
              React.createElement("input", {
                className: "rf-panel-search",
                type: "search",
                value: search,
                placeholder: texts.table_filter_placeholder,
                onChange: (event) => setSearch(event.target.value),
              }),
              React.createElement(
                "label",
                { className: "rf-filter-toggle" },
                React.createElement("input", {
                  type: "checkbox",
                  checked: showLocalDateTables,
                  onChange: (event) => setShowLocalDateTables(event.target.checked),
                }),
                React.createElement(
                  "span",
                  null,
                  texts.toggle_local_date_tables || "Show LocalDate Table tables"
                )
              ),
              React.createElement(
                "div",
                { className: "rf-panel-actions" },
                React.createElement(
                  "button",
                  {
                    type: "button",
                    onClick: () => {
                      setSearch("");
                      applyViewSelection("all", []);
                    },
                  },
                  texts.clear_filter
                )
              ),
              filteredTableNames.length
                ? React.createElement(
                    "div",
                    { className: "rf-filter-list" },
                    filteredTableNames.map((name) =>
                      React.createElement(
                        "label",
                        { key: name, className: "rf-filter-item" },
                        React.createElement("input", {
                          type: "checkbox",
                          checked: selectedTables.includes(name),
                          onChange: () => toggleTable(name),
                        }),
                        React.createElement("span", null, name)
                      )
                    )
                  )
                : React.createElement("div", { className: "rf-filter-empty" }, texts.filter_empty)
            )
          )
        ),
        React.createElement(
          Panel,
          { position: "top-right" },
          React.createElement(
            "details",
            { className: "rf-panel rf-role-panel", ref: rolePanelRef },
            React.createElement(
              "summary",
              null,
              React.createElement(
                "div",
                { className: "rf-panel-title" },
                React.createElement("strong", null, texts.role_panel_toggle || "Table roles"),
                React.createElement("span", null, `${factViews.length} FACT`) 
              ),
              React.createElement("span", { className: "rf-panel-caret" }, "▾")
            ),
            React.createElement(
              "div",
              { className: "rf-panel-body" },
              React.createElement(
                "div",
                { className: "rf-role-grid" },
                React.createElement(
                  "div",
                  { className: "rf-role-group" },
                  React.createElement("label", null, texts.fact_prefixes_label || "Fact prefixes"),
                  React.createElement("input", {
                    type: "text",
                    value: factPrefixesText,
                    onChange: (event) => setFactPrefixesText(event.target.value),
                  })
                ),
                React.createElement(
                  "div",
                  { className: "rf-role-group" },
                  React.createElement("label", null, texts.dim_prefixes_label || "Dimension prefixes"),
                  React.createElement("input", {
                    type: "text",
                    value: dimPrefixesText,
                    onChange: (event) => setDimPrefixesText(event.target.value),
                  })
                ),
                React.createElement(
                  "div",
                  { className: "rf-panel-actions" },
                  React.createElement(
                    "button",
                    { type: "button", onClick: resetPrefixes },
                    texts.reset_prefixes || "Reset prefixes"
                  )
                ),
                React.createElement("input", {
                  className: "rf-panel-search",
                  type: "search",
                  value: roleSearch,
                  placeholder: texts.table_filter_placeholder,
                  onChange: (event) => setRoleSearch(event.target.value),
                }),
                React.createElement(
                  "div",
                  { className: "rf-role-table" },
                  roleFilteredNames.map((name) =>
                    React.createElement(
                      "div",
                      { key: name, className: "rf-role-row" },
                      React.createElement("span", { className: "rf-role-name" }, name),
                      React.createElement(
                        "select",
                        {
                          className: "rf-role-select",
                          value: manualRoles[name] || "auto",
                          onChange: (event) => updateManualRole(name, event.target.value),
                        },
                        roleOptions.map((option) =>
                          React.createElement(
                            "option",
                            { key: option.value, value: option.value },
                            option.value === "auto"
                              ? `${option.label} (${effectiveRoles.get(name) || "other"})`
                              : option.label
                          )
                        )
                      )
                    )
                  )
                )
              )
            )
          )
        )
      )
    )
  );
}

function App({ graph, texts }) {
  return React.createElement(
    ReactFlowProvider,
    null,
    React.createElement(FlowDiagram, { graph, texts })
  );
}

const rootElement = document.getElementById("model-diagram-root");
const propsElement = document.getElementById("model-diagram-props");

if (rootElement && propsElement) {
  const props = JSON.parse(propsElement.textContent);
  createRoot(rootElement).render(
    React.createElement(App, {
      graph: props.graph,
      texts: props.texts,
    })
  );
}


