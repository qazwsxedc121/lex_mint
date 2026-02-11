/**
 * Type definitions for chat folders.
 */

export interface Folder {
  id: string;
  name: string;
  order: number;
}

export interface FolderCreate {
  name: string;
}

export interface FolderUpdate {
  name: string;
}
