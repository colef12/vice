// windows/makeinstaller.go
// Copyright(c) vice contributors, licensed under the GNU Public License, Version 3.
// SPDX: GPL-3.0-only

package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"text/template"
	"unicode"
)

type InstallFile struct {
	Source  string
	Id      string
	KeyPath bool
}

type Release struct {
	Version   string
	FontFiles []InstallFile

	// colef12 fork: the custom-resources directory tree that ships with
	// Vice Custom, as WiX Directory/Component elements, and the ids of
	// its components.
	CustomResourcesXML   string
	CustomResourcesComps []string
}

// customResourcesTree returns WiX markup for the directory tree rooted at
// root, one component per file, and the ids of those components. It
// returns "" if root doesn't exist.
func customResourcesTree(root string) (string, []string) {
	if fi, err := os.Stat(root); err != nil || !fi.IsDir() {
		return "", nil
	}

	var sb strings.Builder
	var comps []string
	ndir := 0
	var walk func(dir, indent string)
	walk = func(dir, indent string) {
		entries, err := os.ReadDir(dir)
		if err != nil {
			panic(err)
		}
		for _, e := range entries {
			p := filepath.Join(dir, e.Name())
			if strings.HasPrefix(e.Name(), ".") {
				continue
			}
			if e.IsDir() {
				ndir++
				fmt.Fprintf(&sb, "%s<Directory Id=\"CRDir%d\" Name=\"%s\">\n", indent, ndir, e.Name())
				walk(p, indent+"  ")
				fmt.Fprintf(&sb, "%s</Directory>\n", indent)
			} else {
				id := fmt.Sprintf("CRFile%d", len(comps)+1)
				fmt.Fprintf(&sb, "%s<Component Id=\"%s\" Guid=\"*\">\n", indent, id)
				fmt.Fprintf(&sb, "%s  <File Id=\"%s\" KeyPath=\"yes\" Name=\"%s\" Source=\"%s\" />\n",
					indent, id, e.Name(), p)
				fmt.Fprintf(&sb, "%s</Component>\n", indent)
				comps = append(comps, id)
			}
		}
	}
	walk(root, "            ")
	return sb.String(), comps
}

func getLatestGitTag() string {
	cmd := exec.Command("git", "describe", "--tags", "--abbrev=0")
	var out bytes.Buffer
	cmd.Stdout = &out
	err := cmd.Run()
	if err != nil {
		panic(err)
	}
	return strings.TrimSpace(out.String())
}

// wixVersion converts a git tag like "v0.14.4" or "v0.14.4-beta2" into a
// WiX-compatible four-field version. Beta N of X.Y.Z uses N as the fourth
// field; the final X.Y.Z uses one more than the highest beta number that
// was ever tagged for X.Y.Z (or 1 if none were).
func wixVersion(tag string) string {
	re := regexp.MustCompile(`^v(\d+)\.(\d+)\.(\d+)(?:-beta(\d+))?$`)
	m := re.FindStringSubmatch(tag)
	if m == nil {
		panic("unexpected tag format: " + tag)
	}
	if m[4] != "" {
		return fmt.Sprintf("%s.%s.%s.%s", m[1], m[2], m[3], m[4])
	}
	return fmt.Sprintf("%s.%s.%s.%d", m[1], m[2], m[3], maxBetaNumber(m[1], m[2], m[3])+1)
}

// maxBetaNumber returns the highest N such that a tag vX.Y.Z-betaN exists in
// the repo, or 0 if none do.
func maxBetaNumber(x, y, z string) int {
	prefix := fmt.Sprintf("v%s.%s.%s-beta", x, y, z)
	cmd := exec.Command("git", "tag", "-l", prefix+"*")
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		panic(err)
	}
	re := regexp.MustCompile(`^` + regexp.QuoteMeta(prefix) + `(\d+)$`)
	max := 0
	for line := range strings.SplitSeq(out.String(), "\n") {
		m := re.FindStringSubmatch(strings.TrimSpace(line))
		if m == nil {
			continue
		}
		n, err := strconv.Atoi(m[1])
		if err == nil && n > max {
			max = n
		}
	}
	return max
}

func main() {
	tag := getLatestGitTag()

	var r Release
	r.Version = wixVersion(tag)

	initFiles := func(globs ...string) []InstallFile {
		var files []InstallFile

		for _, glob := range globs {
			matches, err := filepath.Glob(glob)
			if err != nil {
				panic(err)
			}

			for _, f := range matches {
				id := filepath.Base(f)
				if unicode.IsDigit(rune(id[0])) {
					// Can't start with a digit
					id = "_" + id
				}
				id = strings.Map(func(ch rune) rune {
					if unicode.IsLetter(ch) || unicode.IsDigit(ch) || ch == '.' {
						return ch
					}
					return '_'
				}, id)
				files = append(files, InstallFile{
					Source: strings.ReplaceAll(f, "/", `\\`),
					Id:     id})
			}
		}

		sort.Slice(files, func(i, j int) bool { return files[i].Source < files[j].Source })
		files[0].KeyPath = true

		return files
	}

	r.FontFiles = initFiles("fonts/*.zst")
	r.CustomResourcesXML, r.CustomResourcesComps = customResourcesTree("custom-resources")

	tmpl, err := template.New("installer.wxs").Parse(xmlTemplate)
	if err != nil {
		panic(err)
	}

	if err := tmpl.Execute(os.Stdout, r); err != nil {
		panic(err)
	}

}

const xmlTemplate = `<?xml version='1.0' encoding='utf-8'?>
<Wix xmlns='http://schemas.microsoft.com/wix/2006/wi'>
  <Product Name='Vice Custom'
	   Manufacturer='Matt Pharr'
	   Id='*'
	   UpgradeCode='C489A293-DCD6-4299-B6FA-F4613254CCF0'
	   Language='1033'
	   Codepage='1252'
	   Version='{{.Version}}'
	   >
    <Package Id='*'
    	     Keywords='Installer'
	     Description="Vice Custom Installer"
	     Manufacturer='Matt Pharr'
	     InstallerVersion='100'
	     Languages='1033'
	     Compressed='yes'
	     SummaryCodepage='1252'
	     />

    <MajorUpgrade AllowSameVersionUpgrades="yes" DowngradeErrorMessage="A later version of Vice Custom is already installed. Setup will now exit." />

    <MediaTemplate EmbedCab="yes" />

    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="ProgramFilesFolder">
        <Directory Id="INSTALLFOLDER" Name="Vice Custom">
          <Component Id="ViceExe" Guid='3CFBAA76-3F1B-407A-8700-2937DE63645C'>
            <File KeyPath="yes" Name="Vice.exe" Source="Vice.exe"></File>
          </Component>
          <Component Id="BackshopExe" Guid='68A2028E-D3CF-4082-B40E-821EB14447CE'>
            <File KeyPath="yes" Name="backshop.exe" Source="backshop.exe"></File>
          </Component>
          <Component Id="Crc2viceExe" Guid='1C32032E-ED9E-4288-8611-76A9B6A965D2'>
            <File KeyPath="yes" Name="crc2vice.exe" Source="crc2vice.exe"></File>
          </Component>
          <Component Id="Dat2viceExe" Guid='8E08CC21-D9FF-4576-91B9-B371B55276AB'>
            <File KeyPath="yes" Name="dat2vice.exe" Source="dat2vice.exe"></File>
          </Component>
          <Component Id="ViceserverExe" Guid='F0D03492-717B-46EB-9259-893B1CE012C0'>
            <File KeyPath="yes" Name="viceserver.exe" Source="viceserver.exe"></File>
          </Component>
          <Component Id="SDLDLL" Guid='55630581-E376-4A52-8AA1-0EDD29C887E2'>
            <File KeyPath="yes" Source="windows/SDL2.dll"></File>
          </Component>
          <Component Id="gccseh" Guid='857E2403-D2A6-410C-8F22-9CD7E8536BF5'>
            <File KeyPath="yes" Source="windows/libgcc_s_seh-1.dll"></File>
          </Component>
          <Component Id="libstdcpp" Guid='C590AA03-5D35-4A7C-ADD3-BD5E40B30915'>
            <File KeyPath="yes" Source="windows/libstdc++-6.dll"></File>
          </Component>
          <Component Id="libwinpthread" Guid='E164FA27-C9CC-46CC-863B-9405B62BFE58'>
            <File KeyPath="yes" Source="windows/libwinpthread-1.dll"></File>
          </Component>
          <Component Id="sherpaonnx" Guid='6AD0F03C-7364-4491-8FA0-CE916E7E60AC'>
            <File KeyPath="yes" Source="windows/sherpa-onnx-c-api.dll"></File>
          </Component>
          <Component Id="onnxruntime" Guid='9FBE5C65-00A8-465C-B4F0-010BAC3CA02D'>
            <File KeyPath="yes" Source="windows/onnxruntime.dll"></File>
          </Component>
          <Component Id="vulkanloader" Guid='3EE9D914-6E79-4E3B-A3C3-559782DA3045'>
            <File KeyPath="yes" Source="windows/vulkan-1.dll"></File>
          </Component>
{{if .CustomResourcesXML}}          <Directory Id="CustomResourcesFolder" Name="custom-resources">
{{.CustomResourcesXML}}          </Directory>
{{end}}          <Directory Id="MyFontsFolder" Name="fonts">
            <Component Id="FontsId" Guid="B3D9AC47-25DC-4D6F-B05C-609BC18FDD04">
{{range .FontFiles}}                <File Id="{{.Id}}" Source="{{.Source}}" {{if .KeyPath}}KeyPath="yes" {{end}}/>
{{end}}
            </Component>
          </Directory>
        </Directory>

	<Directory Id="ProgramMenuFolder">
	  <Directory Id="ApplicationProgramsFolder" Name="Vice Custom"/>
	</Directory>

	<Directory Id="DesktopFolder" Name="Desktop">
          <Component Id="ApplicationShortcutDesktop" Guid="*">
            <Shortcut Id="ApplicationDesktopShortcut"
                      Name="Vice Custom"
                      Description="Vice ATC Simulator (custom build)"
                      Target="[#Vice.exe]"
                      WorkingDirectory="INSTALLFOLDER"/>
            <RemoveFolder Id="DesktopFolder" On="uninstall"/>
            <RegistryValue
                Root="HKCU"
                Key="Software\colef12\Vice Custom"
                Name="installed"
                Type="integer"
                Value="1"
                KeyPath="yes"/>
          </Component>
	</Directory>

      </Directory>
    </Directory>

    <UI Id="UserInterface">
      <Property Id="WIXUI_INSTALLDIR" Value="TARGETDIR" />
      <Property Id="WixUI_Mode" Value="Custom" />

      <TextStyle Id="WixUI_Font_Normal" FaceName="Tahoma" Size="8" />
      <TextStyle Id="WixUI_Font_Bigger" FaceName="Tahoma" Size="9" Bold="yes" />
      <TextStyle Id="WixUI_Font_Title"  FaceName="Tahoma" Size="9" Bold="yes" />

      <Property Id="DefaultUIFont" Value="WixUI_Font_Normal" />

      <DialogRef Id="ProgressDlg" />
      <DialogRef Id="ErrorDlg" />
      <DialogRef Id="FilesInUse" />
      <DialogRef Id="FatalError" />
      <DialogRef Id="UserExit" />
      <DialogRef Id="CustomizeDlg" />

      <!-- Welcome, then the feature tree so that backshop can be selected,
           then straight to installing: no license or directory pages. -->
      <Publish Dialog="ExitDialog" Control="Finish" Event="EndDialog" Value="Return" Order="999">1</Publish>
      <Publish Dialog="WelcomeDlg" Control="Next" Event="NewDialog" Value="CustomizeDlg" Order="2">1</Publish>
      <Publish Dialog="CustomizeDlg" Control="Back" Event="NewDialog" Value="WelcomeDlg" Order="1">1</Publish>
      <Publish Dialog="CustomizeDlg" Control="Next" Event="EndDialog" Value="Return" Order="2">1</Publish>

    </UI>
    <UIRef Id="WixUI_Common" />

    <WixVariable Id="WixUIDialogBmp" Value="windows\dialog.bmp" />

    <DirectoryRef Id="ApplicationProgramsFolder">
      <Component Id="ApplicationShortcut" Guid='7A667C90-4B98-4FE4-A65E-BB0B12F935E8'>
        <Shortcut Id="ApplicationStartMenuShortcut"
                  Name="Vice Custom"
                  Description="ATC Simulator (custom build)"
                  Target="[#Vice.exe]"
                  WorkingDirectory="INSTALLFOLDER"/>
        <RemoveFolder Id="ApplicationProgramsFolder" On="uninstall"/>
        <RegistryValue Root="HKCU" Key="Software\colef12\Vice Custom" Name="installed" Type="integer" Value="1" KeyPath="yes"/>
      </Component>
      <Component Id="BackshopShortcut" Guid='6348FAB5-4D8B-4729-B73D-62E4AAAC397B'>
        <Shortcut Id="BackshopStartMenuShortcut"
                  Name="Backshop (Vice Custom)"
                  Description="vice facility engineering tool"
                  Target="[#backshop.exe]"
                  WorkingDirectory="INSTALLFOLDER"/>
        <RemoveFolder Id="BackshopProgramsFolder" Directory="ApplicationProgramsFolder" On="uninstall"/>
        <RegistryValue Root="HKCU" Key="Software\colef12\Vice Custom" Name="backshop" Type="integer" Value="1" KeyPath="yes"/>
      </Component>
    </DirectoryRef>

    <Feature Id="MyFeature" Title="Vice" Description="The vice ATC simulator and its map conversion tools."
             Level="1" Absent="disallow" AllowAdvertise="no">
      <ComponentRef Id="ViceExe" />
      <ComponentRef Id="Crc2viceExe" />
      <ComponentRef Id="Dat2viceExe" />
      <ComponentRef Id="ViceserverExe" />
      <ComponentRef Id="SDLDLL" />
      <ComponentRef Id="gccseh" />
      <ComponentRef Id="libstdcpp" />
      <ComponentRef Id="libwinpthread" />
      <ComponentRef Id="sherpaonnx" />
      <ComponentRef Id="onnxruntime" />
      <ComponentRef Id="vulkanloader" />
      <ComponentRef Id="FontsId" />
{{range .CustomResourcesComps}}      <ComponentRef Id="{{.}}" />
{{end}}
      <ComponentRef Id="ApplicationShortcut" />
      <ComponentRef Id="ApplicationShortcutDesktop" />
    </Feature>

    <!-- Level 2 keeps backshop unselected by default; it is for people
         developing scenarios rather than for people flying them. -->
    <Feature Id="Backshop" Title="Facility engineering tool"
             Description="backshop, for developing scenarios, facility configurations, and video maps."
             Level="2" AllowAdvertise="no">
      <ComponentRef Id="BackshopExe" />
      <ComponentRef Id="BackshopShortcut" />
    </Feature>
  </Product>
</Wix>
`
