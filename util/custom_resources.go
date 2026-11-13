// util/custom_resources.go
// Copyright(c) vice contributors, licensed under the GNU Public License, Version 3.
// SPDX: GPL-3.0-only

// colef12 fork ("Vice Custom"): resource files that ship with this build.

package util

import (
	"io/fs"
	"os"
	"path/filepath"
)

// CustomResourcesDirName is the directory next to the executable that holds
// the scenarios, facility configurations, and other resource files that
// ship with Vice Custom. It is organized like the resources directory and
// layered on top of it, below any overlay directory the user selects.
const CustomResourcesDirName = "custom-resources"

// CustomResourcesDir returns the directory of the resource files that ship
// with this build, or "" if there isn't one. VICE_CUSTOM_RESOURCES, if set,
// names it in place of the one next to the executable.
func CustomResourcesDir() string {
	if dir := os.Getenv("VICE_CUSTOM_RESOURCES"); dir != "" {
		if IsDir(dir) {
			return dir
		}
		return ""
	}
	exe, err := os.Executable()
	if err != nil {
		return ""
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	if dir := filepath.Join(filepath.Dir(exe), CustomResourcesDirName); IsDir(dir) {
		return dir
	}
	return ""
}

// withCustomResources layers the custom resources directory, if there is
// one, on top of base.
func withCustomResources(base *fs.StatFS) *fs.StatFS {
	dir := CustomResourcesDir()
	if dir == "" {
		return base
	}
	var layered fs.StatFS = overlayFS{base: *base, overlay: os.DirFS(dir), opened: &pathSet{}}
	return &layered
}
