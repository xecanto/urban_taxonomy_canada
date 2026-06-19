export interface LayerSymbology {
  colorBy: string;        // "level_1".."level_7" | "HEIGHT" | "BLDG_POP" | "solid"
  ramp: string;
  opacity: number;
  visible: boolean;
}

export interface TreeNode {
  id: string;
  leaf: boolean;
  distance: number;
  count: number;
  children?: TreeNode[];
  [key: string]: any;
}

export interface HierarchyData {
  tree: TreeNode;
  trees: Record<string, TreeNode>;
  cluster_summary: Record<string, { cluster: number; morphotopes: number }[]>;
  levels: string[];
  total_morphotopes: number;
}
