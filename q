_C_M_A_K_E(1)                                                                                                            CMake                                                                                                            _C_M_A_K_E(1)

NNAAMMEE
       cmake - CMake Command-Line Reference

SSYYNNOOPPSSIISS
          Generate a Project Buildsystem
           cmake [<options>] -B <path-to-build> [-S <path-to-source>]
           cmake [<options>] <path-to-source | path-to-existing-build>

          Build a Project
           cmake --build <dir> [<options>] [-- <build-tool-options>]

          Install a Project
           cmake --install <dir> [<options>]

          Open a Project
           cmake --open <dir>

          Run a Script
           cmake [-D <var>=<value>]... -P <cmake-script-file>

          Run a Command-Line Tool
           cmake -E <command> [<options>]

          Run the Find-Package Tool
           cmake --find-package [<options>]

          Run a Workflow Preset
           cmake --workflow <options>

          View Help
           cmake --help[-<topic>]

DDEESSCCRRIIPPTTIIOONN
       The ccmmaakkee executable is the command-line interface of the cross-platform buildsystem generator CMake.  The above Synopsis lists various actions the tool can perform as described in sections below.

       To  build  a  software  project with CMake, Generate a Project Buildsystem.  Optionally use ccmmaakkee to Build a Project, Install a Project or just run the corresponding build tool (e.g. mmaakkee) directly.  ccmmaakkee can also be used to View
       Help.

       The other actions are meant for use by software developers writing scripts in the CCMMaakkee llaanngguuaaggee <#manual:cmake-language(7)> to support their builds.

       For graphical user interfaces that may be used in place of ccmmaakkee, see ccccmmaakkee <#manual:ccmake(1)> and ccmmaakkee--gguuii <#manual:cmake-gui(1)>.  For command-line interfaces to the CMake  testing  and  packaging  facilities,  see  cctteesstt  <#
       manual:ctest(1)> and ccppaacckk <#manual:cpack(1)>.

       For more information on CMake at large, see also the links at the end of this manual.

IINNTTRROODDUUCCTTIIOONN TTOO CCMMAAKKEE BBUUIILLDDSSYYSSTTEEMMSS
       A  _b_u_i_l_d_s_y_s_t_e_m  describes how to build a project's executables and libraries from its source code using a _b_u_i_l_d _t_o_o_l to automate the process.  For example, a buildsystem may be a MMaakkeeffiillee for use with a command-line mmaakkee tool or a
       project file for an Integrated Development Environment (IDE).  In order to avoid maintaining multiple such  buildsystems,  a  project  may  specify  its  buildsystem  abstractly  using  files  written  in  the  CCMMaakkee  llaanngguuaaggee  <#
       manual:cmake-language(7)>.  From these files CMake generates a preferred buildsystem locally for each user through a backend called a _g_e_n_e_r_a_t_o_r.

       To generate a buildsystem with CMake, the following must be selected:

       SSoouurrccee TTrreeee
              The top-level directory containing source files provided by the project.  The project specifies its buildsystem using files as described in the ccmmaakkee--llaanngguuaaggee((77)) <#manual:cmake-language(7)> manual, starting with a top-level
              file named CCMMaakkeeLLiissttss..ttxxtt.  These files specify build targets and their dependencies as described in the ccmmaakkee--bbuuiillddssyysstteemm((77)) <#manual:cmake-buildsystem(7)> manual.

       BBuuiilldd TTrreeee
              The  top-level  directory  in which buildsystem files and build output artifacts (e.g. executables and libraries) are to be stored.  CMake will write a CCMMaakkeeCCaacchhee..ttxxtt file to identify the directory as a build tree and store
              persistent information such as buildsystem configuration options.

              To maintain a pristine source tree, perform an _o_u_t_-_o_f_-_s_o_u_r_c_e build by using a separate dedicated build tree.  An _i_n_-_s_o_u_r_c_e build in which the build tree is placed in the same directory as the source tree is also  supported,
              but discouraged.

       GGeenneerraattoorr
              This  chooses the kind of buildsystem to generate.  See the ccmmaakkee--ggeenneerraattoorrss((77)) <#manual:cmake-generators(7)> manual for documentation of all generators.  Run ccmmaakkee ----hheellpp to see a list of generators available locally.  Op‐
              tionally use the --GG option below to specify a generator, or simply accept the default CMake chooses for the current platform.

              When using one of the Command-Line Build Tool Generators <#command-line-build-tool-generators> CMake expects that the environment needed by the compiler toolchain is already configured in the shell.  When using one  of  the
              IDE Build Tool Generators <#ide-build-tool-generators>, no particular environment is needed.

GGEENNEERRAATTEE AA PPRROOJJEECCTT BBUUIILLDDSSYYSSTTEEMM
       Run CMake with one of the following command signatures to specify the source and build trees and generate a buildsystem:

       ccmmaakkee [[<<ooppttiioonnss>>]] --BB <<ppaatthh--ttoo--bbuuiilldd>> [[--SS <<ppaatthh--ttoo--ssoouurrccee>>]]
          Added in version 3.13.

          Uses  <<ppaatthh--ttoo--bbuuiilldd>> as the build tree and <<ppaatthh--ttoo--ssoouurrccee>> as the source tree.  The specified paths may be absolute or relative to the current working directory.  The source tree must contain a CCMMaakkeeLLiissttss..ttxxtt file.  The build
          tree will be created automatically if it does not already exist.  For example:

              $ cmake -S src -B build

       ccmmaakkee [[<<ooppttiioonnss>>]] <<ppaatthh--ttoo--ssoouurrccee>>
              Uses the current working directory as the build tree, and <<ppaatthh--ttoo--ssoouurrccee>> as the source tree.  The specified path may be absolute or relative to the current working directory.  The source tree must contain a CCMMaakkeeLLiissttss..ttxxtt
              file and must _n_o_t contain a CCMMaakkeeCCaacchhee..ttxxtt file because the latter identifies an existing build tree.  For example:

                 $ mkdir build ; cd build
                 $ cmake ../src

       ccmmaakkee [[<<ooppttiioonnss>>]] <<ppaatthh--ttoo--eexxiissttiinngg--bbuuiilldd>>
              Uses <<ppaatthh--ttoo--eexxiissttiinngg--bbuuiilldd>> as the build tree, and loads the path to the source tree from its CCMMaakkeeCCaacchhee..ttxxtt file, which must have already been generated by a previous run of CMake.  The specified path may be absolute  or
              relative to the current working directory.  For example:

                 $ cd build
                 $ cmake .

       In all cases the <<ooppttiioonnss>> may be zero or more of the Options below.

       The  above  styles  for specifying the source and build trees may be mixed.  Paths specified with --SS or --BB are always classified as source or build trees, respectively.  Paths specified with plain arguments are classified based on
       their content and the types of paths given earlier.  If only one type of path is given, the current working directory (cwd) is used for the other.  For example:
                                                                                                ┌────────────────────────┬────────────┬───────────┐
                                                                                                │ Command Line           │ Source Dir │ Build Dir │
                                                                                                ├────────────────────────┼────────────┼───────────┤
                                                                                                │ ccmmaakkee --BB bbuuiilldd         │ _c_w_d        │ bbuuiilldd     │
                                                                                                ├────────────────────────┼────────────┼───────────┤
                                                                                                │ ccmmaakkee --BB bbuuiilldd ssrrcc     │ ssrrcc        │ bbuuiilldd     │
                                                                                                ├────────────────────────┼────────────┼───────────┤
                                                                                                │ ccmmaakkee --BB bbuuiilldd --SS ssrrcc  │ ssrrcc        │ bbuuiilldd     │
                                                                                                ├────────────────────────┼────────────┼───────────┤
                                                                                                │ ccmmaakkee ssrrcc              │ ssrrcc        │ _c_w_d       │
                                                                                                ├────────────────────────┼────────────┼───────────┤
                                                                                                │ ccmmaakkee bbuuiilldd (existing) │ _l_o_a_d_e_d     │ bbuuiilldd     │
                                                                                                ├────────────────────────┼────────────┼───────────┤
                                                                                                │ ccmmaakkee --SS ssrrcc           │ ssrrcc        │ _c_w_d       │
                                                                                                ├────────────────────────┼────────────┼───────────┤
                                                                                                │ ccmmaakkee --SS ssrrcc bbuuiilldd     │ ssrrcc        │ bbuuiilldd     │
                                                                                                ├────────────────────────┼────────────┼───────────┤
                                                                                                │ ccmmaakkee --SS ssrrcc --BB bbuuiilldd  │ ssrrcc        │ bbuuiilldd     │
                                                                                                └────────────────────────┴────────────┴───────────┘

       Changed in version 3.23: CMake warns when multiple source paths are specified.  This has never been officially documented or supported, but older versions accidentally accepted multiple source paths and used the last  path  speci‐
       fied.  Avoid passing multiple source path arguments.

       After generating a buildsystem one may use the corresponding native build tool to build the project.  For example, after using the UUnniixx MMaakkeeffiilleess <#generator:Unix Makefiles> generator one may run mmaakkee directly:

              $ make
              $ make install

       Alternatively, one may use ccmmaakkee to Build a Project by automatically choosing and invoking the appropriate native build tool.

   OOppttiioonnss
       --SS <<ppaatthh--ttoo--ssoouurrccee>>
              Path to root directory of the CMake project to build.

       --BB <<ppaatthh--ttoo--bbuuiilldd>>
              Path to directory which CMake will use as the root of build directory.

              If the directory doesn't already exist CMake will make it.

       --CC <<iinniittiiaall--ccaacchhee>>
              Pre-load a script to populate the cache.

              When  CMake  is first run in an empty build tree, it creates a CCMMaakkeeCCaacchhee..ttxxtt file and populates it with customizable settings for the project.  This option may be used to specify a file from which to load cache entries be‐
              fore the first pass through the project's CMake listfiles.  The loaded entries take priority over the project's default values.  The given file should be a CMake script containing sseett(()) <#command:set> commands that use  the
              CCAACCHHEE option, not a cache-format file.

              References to CCMMAAKKEE__SSOOUURRCCEE__DDIIRR <#variable:CMAKE_SOURCE_DIR> and CCMMAAKKEE__BBIINNAARRYY__DDIIRR <#variable:CMAKE_BINARY_DIR> within the script evaluate to the top-level source and build tree.

       --DD <<vvaarr>>::<<ttyyppee>>==<<vvaalluuee>>,, --DD <<vvaarr>>==<<vvaalluuee>>
              Create or update a CMake CCAACCHHEE entry.

              When  CMake  is  first  run  in  an  empty build tree, it creates a CCMMaakkeeCCaacchhee..ttxxtt file and populates it with customizable settings for the project.  This option may be used to specify a setting that takes priority over the
              project's default value.  The option may be repeated for as many CCAACCHHEE entries as desired.

              If the ::<<ttyyppee>> portion is given it must be one of the types specified by the sseett(()) <#command:set> command documentation for its CCAACCHHEE signature.  If the ::<<ttyyppee>> portion is omitted the entry will be created with no  type  if
              it does not exist with a type already.  If a command in the project sets the type to PPAATTHH or FFIILLEEPPAATTHH then the <<vvaalluuee>> will be converted to an absolute path.

              This option may also be given as a single argument: --DD<<vvaarr>>::<<ttyyppee>>==<<vvaalluuee>> or --DD<<vvaarr>>==<<vvaalluuee>>.

              It's  important to note that the order of --CC and --DD arguments is significant. They will be carried out in the order they are listed, with the last argument taking precedence over the previous ones. For example, if you spec‐
              ify --DDCCMMAAKKEE__BBUUIILLDD__TTYYPPEE==DDeebbuugg, followed by a --CC argument with a file that calls:

                 set(CMAKE_BUILD_TYPE "Release" CACHE STRING "" FORCE)

              then the --CC argument will take precedence, and CCMMAAKKEE__BBUUIILLDD__TTYYPPEE will be set to RReelleeaassee. However, if the --DD argument comes after the --CC argument, it will be set to DDeebbuugg.

              If a sseett((...... CCAACCHHEE ......)) call in the --CC file does not use FFOORRCCEE, and a --DD argument sets the same variable, the --DD argument will take precedence regardless of order because of the nature of non-FFOORRCCEE sseett((...... CCAACCHHEE ......)) calls.

       --UU <<gglloobbbbiinngg__eexxpprr>>
              Remove matching entries from CMake CCAACCHHEE.

              This option may be used to remove one or more variables from the CCMMaakkeeCCaacchhee..ttxxtt file, globbing expressions using ** and ?? are supported.  The option may be repeated for as many CCAACCHHEE entries as desired.

              Use with care, you can make your CCMMaakkeeCCaacchhee..ttxxtt non-working.

       --GG <<ggeenneerraattoorr--nnaammee>>
              Specify a build system generator.

              CMake may support multiple native build systems on certain platforms.  A generator is responsible for  generating  a  particular  build  system.   Possible  generator  names  are  specified  in  the  ccmmaakkee--ggeenneerraattoorrss((77))  <#
              manual:cmake-generators(7)> manual.

              If not specified, CMake checks the CCMMAAKKEE__GGEENNEERRAATTOORR <#envvar:CMAKE_GENERATOR> environment variable and otherwise falls back to a builtin default selection.

       --TT <<ttoooollsseett--ssppeecc>>
              Toolset specification for the generator, if supported.

              Some CMake generators support a toolset specification to tell the native build system how to choose a compiler.  See the CCMMAAKKEE__GGEENNEERRAATTOORR__TTOOOOLLSSEETT <#variable:CMAKE_GENERATOR_TOOLSET> variable for details.

       --AA <<ppllaattffoorrmm--nnaammee>>
              Specify platform name if supported by generator.

              Some CMake generators support a platform name to be given to the native build system to choose a compiler or SDK.  See the CCMMAAKKEE__GGEENNEERRAATTOORR__PPLLAATTFFOORRMM <#variable:CMAKE_GENERATOR_PLATFORM> variable for details.

       ----ttoooollcchhaaiinn <<ppaatthh--ttoo--ffiillee>>
              Added in version 3.21.

              Specify the cross compiling toolchain file, equivalent to setting CCMMAAKKEE__TTOOOOLLCCHHAAIINN__FFIILLEE <#variable:CMAKE_TOOLCHAIN_FILE> variable. Relative paths are interpreted as relative to the build directory, and if not found, relative
              to the source directory.

       ----iinnssttaallll--pprreeffiixx <<ddiirreeccttoorryy>>
              Added in version 3.21.

              Specify the installation directory, used by the CCMMAAKKEE__IINNSSTTAALLLL__PPRREEFFIIXX <#variable:CMAKE_INSTALL_PREFIX> variable. Must be an absolute path.

       ----pprroojjeecctt--ffiillee <<pprroojjeecctt--ffiillee--nnaammee>>
              Added in version 4.0.

              Specify an alternate project file name.

              This determines the top-level file processed by CMake when configuring a project, and the file processed by aadddd__ssuubbddiirreeccttoorryy(()) <#command:add_subdirectory>.

              By default, this is CCMMaakkeeLLiissttss..ttxxtt. If set to anything else, CCMMaakkeeLLiissttss..ttxxtt will be used as a fallback whenever the specified file cannot be found within a project subdirectory.

              NNoottee::
                 This  feature  is intended for temporary use by developers during an incremental transition and not for publication of a final product. CMake will always emit a warning when the project file is anything other than CCMMaakkee‐‐
                 LLiissttss..ttxxtt.

       --WWnnoo--ddeevv
              Suppress developer warnings.

              Suppress warnings that are meant for the author of the CCMMaakkeeLLiissttss..ttxxtt files. By default this will also turn off deprecation warnings.

       --WWddeevv  Enable developer warnings.

              Enable warnings that are meant for the author of the CCMMaakkeeLLiissttss..ttxxtt files. By default this will also turn on deprecation warnings.

       --WWddeepprreeccaatteedd
              Enable deprecated functionality warnings.

              Enable warnings for usage of deprecated functionality, that are meant for the author of the CCMMaakkeeLLiissttss..ttxxtt files.

       --WWnnoo--ddeepprreeccaatteedd
              Suppress deprecated functionality warnings.

              Suppress warnings for usage of deprecated functionality, that are meant for the author of the CCMMaakkeeLLiissttss..ttxxtt files.

       --WWeerrrroorr==<<wwhhaatt>>
              Treat CMake warnings as errors. <<wwhhaatt>> must be one of the following:

              ddeevv    Make developer warnings errors.

                     Make warnings that are meant for the author of the CCMMaakkeeLLiissttss..ttxxtt files errors. By default this will also turn on deprecated warnings as errors.

              ddeepprreeccaatteedd
                     Make deprecated macro and function warnings errors.

                     Make warnings for usage of deprecated macros and functions, that are meant for the author of the CCMMaakkeeLLiissttss..ttxxtt files, errors.

       --WWnnoo--eerrrroorr==<<wwhhaatt>>
              Do not treat CMake warnings as errors. <<wwhhaatt>> must be one of the following:

              ddeevv    Make warnings that are meant for the author of the CCMMaakkeeLLiissttss..ttxxtt files not errors. By default this will also turn off deprecated warnings as errors.

              ddeepprreeccaatteedd
                     Make warnings for usage of deprecated macros and functions, that are meant for the author of the CCMMaakkeeLLiissttss..ttxxtt files, not errors.

       ----ffrreesshh
              Added in version 3.24.

              Perform a fresh configuration of the build tree.  This removes any existing CCMMaakkeeCCaacchhee..ttxxtt file and associated CCMMaakkeeFFiilleess// directory, and recreates them from scratch.

              Changed in version 3.30: For dependencies previously populated by FFeettcchhCCoonntteenntt <#module:FetchContent> with the NNEEWW setting for policy CCMMPP00116688 <#policy:CMP0168>, their stamp and script files from any previous run will be re‐
              moved. The download, update, and patch steps will therefore be forced to re-execute.

       --LL[[AA]][[HH]]
              List non-advanced cached variables.

              List CCAACCHHEE variables will run CMake and list all the variables from the CMake CCAACCHHEE that are not marked as IINNTTEERRNNAALL or AADDVVAANNCCEEDD <#prop_cache:ADVANCED>.  This will effectively display current CMake settings, which  can  then
              be changed with --DD option.  Changing some of the variables may result in more variables being created.  If AA is specified, then it will display also advanced variables.  If HH is specified, it will also display help for each
              variable.

       --LLRR[[AA]][[HH]] <<rreeggeexx>>
              Added in version 3.31.

              Show specific non-advanced cached variables

              Show  non-IINNTTEERRNNAALL  nor  AADDVVAANNCCEEDD <#prop_cache:ADVANCED> variables from the CMake CCAACCHHEE that match the given regex. If AA is specified, then it will also show advanced variables.  If HH is specified, it will also display help
              for each variable.

       --NN     View mode only.

              Only load the cache.  Do not actually run configure and generate steps.

       ----ggrraapphhvviizz==<<ffiillee>>
              Generate Graphviz <https://www.graphviz.org/> of dependencies

              This option generates a graphviz input file that will contain all the library and executable dependencies in the project showing the dependencies between the targets in a project, as well as  external  libraries  which  are
              linked against.

              When running CMake with the ----ggrraapphhvviizz==ffoooo..ddoott option, it produces:

              • a ffoooo..ddoott file, showing all dependencies in the project

              • a ffoooo..ddoott..<<ttaarrggeett>> file for each target, showing on which other targets it depends

              • a ffoooo..ddoott..<<ttaarrggeett>>..ddeeppeennddeerrss file for each target, showing which other targets depend on it

              Those .dot files can be converted to images using the _d_o_t command from the Graphviz package:

                 dot -Tpng -o foo.png foo.dot

              Added in version 3.10: The different dependency types PPUUBBLLIICC, IINNTTEERRFFAACCEE and PPRRIIVVAATTEE are represented as solid, dashed and dotted edges.

              Variables specific to the Graphviz support

              The resulting graphs can be huge.  The look and content of the generated graphs can be controlled using the file CCMMaakkeeGGrraapphhVViizzOOppttiioonnss..ccmmaakkee.  This file is first searched in CCMMAAKKEE__BBIINNAARRYY__DDIIRR <#variable:CMAKE_BINARY_DIR>, and
              then in CCMMAAKKEE__SSOOUURRCCEE__DDIIRR <#variable:CMAKE_SOURCE_DIR>.  If found, the variables set in it are used to adjust options for the generated Graphviz files.

              GGRRAAPPHHVVIIZZ__GGRRAAPPHH__NNAAMMEE
                     The graph name.

                     • Mandatory: NO

                     • Default: value of CCMMAAKKEE__PPRROOJJEECCTT__NNAAMMEE <#variable:CMAKE_PROJECT_NAME>

              GGRRAAPPHHVVIIZZ__GGRRAAPPHH__HHEEAADDEERR
                     The header written at the top of the Graphviz files.

                     • Mandatory: NO

                     • Default: "node [ fontsize = "12" ];"

              GGRRAAPPHHVVIIZZ__NNOODDEE__PPRREEFFIIXX
                     The prefix for each node in the Graphviz files.

                     • Mandatory: NO

                     • Default: "node"

              GGRRAAPPHHVVIIZZ__EEXXEECCUUTTAABBLLEESS
                     Set to FALSE to exclude executables from the generated graphs.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__SSTTAATTIICC__LLIIBBSS
                     Set to FALSE to exclude static libraries from the generated graphs.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__SSHHAARREEDD__LLIIBBSS
                     Set to FALSE to exclude shared libraries from the generated graphs.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__MMOODDUULLEE__LLIIBBSS
                     Set to FALSE to exclude module libraries from the generated graphs.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__IINNTTEERRFFAACCEE__LLIIBBSS
                     Set to FALSE to exclude interface libraries from the generated graphs.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__OOBBJJEECCTT__LLIIBBSS
                     Set to FALSE to exclude object libraries from the generated graphs.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__UUNNKKNNOOWWNN__LLIIBBSS
                     Set to FALSE to exclude unknown libraries from the generated graphs.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__EEXXTTEERRNNAALL__LLIIBBSS
                     Set to FALSE to exclude external libraries from the generated graphs.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__CCUUSSTTOOMM__TTAARRGGEETTSS
                     Set to TRUE to include custom targets in the generated graphs.

                     • Mandatory: NO

                     • Default: FALSE

              GGRRAAPPHHVVIIZZ__IIGGNNOORREE__TTAARRGGEETTSS
                     A list of regular expressions for names of targets to exclude from the generated graphs.

                     • Mandatory: NO

                     • Default: empty

              GGRRAAPPHHVVIIZZ__GGEENNEERRAATTEE__PPEERR__TTAARRGGEETT
                     Set to FALSE to not generate per-target graphs ffoooo..ddoott..<<ttaarrggeett>>.

                     • Mandatory: NO

                     • Default: TRUE

              GGRRAAPPHHVVIIZZ__GGEENNEERRAATTEE__DDEEPPEENNDDEERRSS
                     Set to FALSE to not generate depender graphs ffoooo..ddoott..<<ttaarrggeett>>..ddeeppeennddeerrss.

                     • Mandatory: NO

                     • Default: TRUE

       ----ssyysstteemm--iinnffoorrmmaattiioonn [[ffiillee]]
              Dump information about this system.

              Dump a wide range of information about the current system.  If run from the top of a binary tree for a CMake project it will dump additional information such as the cache, log files etc.

       ----pprriinntt--ccoonnffiigg--ddiirr
              Added in version 3.31.

              Print CMake config directory for user-wide FileAPI queries.

              See CCMMAAKKEE__CCOONNFFIIGG__DDIIRR <#envvar:CMAKE_CONFIG_DIR> for more details.

       ----lloogg--lleevveell==<<lleevveell>>
              Added in version 3.16.

              Set the log <<lleevveell>>.

              The mmeessssaaggee(()) <#command:message> command will only output messages of the specified log level or higher.  The valid log levels are EERRRROORR, WWAARRNNIINNGG, NNOOTTIICCEE, SSTTAATTUUSS (default), VVEERRBBOOSSEE, DDEEBBUUGG, or TTRRAACCEE.

              To  make a log level persist between CMake runs, set CCMMAAKKEE__MMEESSSSAAGGEE__LLOOGG__LLEEVVEELL <#variable:CMAKE_MESSAGE_LOG_LEVEL> as a cache variable instead.  If both the command line option and the variable are given, the command line op‐
              tion takes precedence.

              For backward compatibility reasons, ----lloogglleevveell is also accepted as a synonym for this option.

              Added in version 3.25: See the ccmmaakkee__llaanngguuaaggee(()) <#command:cmake_language> command for a way to query the current message logging level <#query-message-log-level>.

       ----lloogg--ccoonntteexxtt
              Enable the mmeessssaaggee(()) <#command:message> command outputting context attached to each message.

              This option turns on showing context for the current CMake run only.  To make showing the context persistent for all subsequent CMake runs, set CCMMAAKKEE__MMEESSSSAAGGEE__CCOONNTTEEXXTT__SSHHOOWW <#variable:CMAKE_MESSAGE_CONTEXT_SHOW>  as  a  cache
              variable instead.  When this command line option is given, CCMMAAKKEE__MMEESSSSAAGGEE__CCOONNTTEEXXTT__SSHHOOWW <#variable:CMAKE_MESSAGE_CONTEXT_SHOW> is ignored.

       ----ssaarriiff--oouuttppuutt==<<ppaatthh>>
              Added in version 4.0.

              Enable logging of diagnostic messages produced by CMake in the SARIF format.

              Write diagnostic messages to a SARIF file at the path specified. Projects can also set CCMMAAKKEE__EEXXPPOORRTT__SSAARRIIFF <#variable:CMAKE_EXPORT_SARIF> to OONN to enable this feature for a build tree.

       ----ddeebbuugg--ttrryyccoommppiillee
              Do not delete the files and directories created for ttrryy__ccoommppiillee(()) <#command:try_compile> / ttrryy__rruunn(()) <#command:try_run> calls.  This is useful in debugging failed checks.

              Note that some uses of ttrryy__ccoommppiillee(()) <#command:try_compile> may use the same build tree, which will limit the usefulness of this option if a project executes more than one ttrryy__ccoommppiillee(()) <#command:try_compile>.  For example,
              such uses may change results as artifacts from a previous try-compile may cause a different test to either pass or fail incorrectly.  This option is best used only when debugging.

              (With respect to the preceding, the ttrryy__rruunn(()) <#command:try_run> command is effectively a ttrryy__ccoommppiillee(()) <#command:try_compile>.  Any combination of the two is subject to the potential issues described.)

              Added in version 3.25: When this option is enabled, every try-compile check prints a log message reporting the directory in which the check is performed.

       ----ddeebbuugg--oouuttppuutt
              Put cmake in a debug mode.

              Print extra information during the cmake run like stack traces with mmeessssaaggee((SSEENNDD__EERRRROORR)) <#command:message> calls.

       ----ddeebbuugg--ffiinndd
              Added in version 3.17.

              Put cmake find commands in a debug mode.

              Print  extra find call information during the cmake run to standard error. Output is designed for human consumption and not for parsing.  See also the CCMMAAKKEE__FFIINNDD__DDEEBBUUGG__MMOODDEE <#variable:CMAKE_FIND_DEBUG_MODE> variable for de‐
              bugging a more local part of the project.

       ----ddeebbuugg--ffiinndd--ppkkgg==<<ppkkgg>>[[,,......]]
              Added in version 3.23.

              Put cmake find commands in a debug mode when running under calls to ffiinndd__ppaacckkaaggee((<<ppkkgg>>)) <#command:find_package>, where <<ppkkgg>> is an entry in the given comma-separated list of case-sensitive package names.

              Like ----ddeebbuugg--ffiinndd, but limiting scope to the specified packages.

       ----ddeebbuugg--ffiinndd--vvaarr==<<vvaarr>>[[,,......]]
              Added in version 3.23.

              Put cmake find commands in a debug mode when called with <<vvaarr>> as the result variable, where <<vvaarr>> is an entry in the given comma-separated list.

              Like ----ddeebbuugg--ffiinndd, but limiting scope to the specified variable names.

       ----ttrraaccee
              Put cmake in trace mode.

              Print a trace of all calls made and from where.

       ----ttrraaccee--eexxppaanndd
              Put cmake in trace mode.

              Like ----ttrraaccee, but with variables expanded.

       ----ttrraaccee--ffoorrmmaatt==<<ffoorrmmaatt>>
              Added in version 3.17.

              Put cmake in trace mode and sets the trace output format.

              <<ffoorrmmaatt>> can be one of the following values.

                 hhuummaann  Prints each trace line in a human-readable format. This is the default format.

                 jjssoonn--vv11
                        Prints each line as a separate JSON document. Each document is separated by a newline (\\nn). It is guaranteed that no newline characters will be present inside a JSON document.

                        JSON trace format

                            {
                              "file": "/full/path/to/the/CMake/file.txt",
                              "line": 0,
                              "cmd": "add_executable",
                              "args": ["foo", "bar"],
                              "time": 1579512535.9687231,
                              "frame": 2,
                              "global_frame": 4
                            }

                        The members are:

                        ffiillee   The full path to the CMake source file where the function was called.

                        lliinnee   The line in ffiillee where the function call begins.

                        lliinnee__eenndd
                               If the function call spans multiple lines, this field will be set to the line where the function call ends. If the function calls spans a single line, this field will be unset. This field was added in minor
                               version 2 of the jjssoonn--vv11 format.

                        ddeeffeerr  Optional member that is present when the function call was deferred by ccmmaakkee__llaanngguuaaggee((DDEEFFEERR)) <#defer>.  If present, its value is a string containing the deferred call <<iidd>>.

                        ccmmdd    The name of the function that was called.

                        aarrggss   A string list of all function parameters.

                        ttiimmee   Timestamp (seconds since epoch) of the function call.

                        ffrraammee  Stack frame depth of the function that was called, within the context of the  CCMMaakkeeLLiissttss..ttxxtt being processed currently.

                        gglloobbaall__ffrraammee
                               Stack frame depth of the function that was called, tracked globally across all CCMMaakkeeLLiissttss..ttxxtt files involved in the trace. This field was added in minor version 2 of the jjssoonn--vv11 format.

                        Additionally, the first JSON document outputted contains the vveerrssiioonn key for the current major and minor version of the

                        JSON version format

                            {
                              "version": {
                                "major": 1,
                                "minor": 2
                              }
                            }

                        The members are:

                        vveerrssiioonn
                               Indicates the version of the JSON format. The version has a major and minor components following semantic version conventions.

       ----ttrraaccee--ssoouurrccee==<<ffiillee>>
              Put cmake in trace mode, but output only lines of a specified file.

              Multiple options are allowed.

       ----ttrraaccee--rreeddiirreecctt==<<ffiillee>>
              Put cmake in trace mode and redirect trace output to a file instead of stderr.

       ----wwaarrnn--uunniinniittiiaalliizzeedd
              Warn about uninitialized values.

              Print a warning when an uninitialized variable is used.

       ----wwaarrnn--uunnuusseedd--vvaarrss
              Does nothing.  In CMake versions 3.2 and below this enabled warnings about unused variables.  In CMake versions 3.3 through 3.18 the option was broken.  In CMake 3.19 and above the option has been removed.

       ----nnoo--wwaarrnn--uunnuusseedd--ccllii
              Don't warn about command line options.

              Don't find variables that are declared on the command line, but not used.

       ----cchheecckk--ssyysstteemm--vvaarrss
              Find problems with variable usage in system files.

              Normally, unused and uninitialized variables are searched for only in CCMMAAKKEE__SSOOUURRCCEE__DDIIRR <#variable:CMAKE_SOURCE_DIR> and CCMMAAKKEE__BBIINNAARRYY__DDIIRR <#variable:CMAKE_BINARY_DIR>.  This flag tells CMake to  warn  about  other  files  as
              well.

       ----ccoommppiillee--nnoo--wwaarrnniinngg--aass--eerrrroorr
              Added in version 3.24.

              Ignore  target  property CCOOMMPPIILLEE__WWAARRNNIINNGG__AASS__EERRRROORR <#prop_tgt:COMPILE_WARNING_AS_ERROR> and variable CCMMAAKKEE__CCOOMMPPIILLEE__WWAARRNNIINNGG__AASS__EERRRROORR <#variable:CMAKE_COMPILE_WARNING_AS_ERROR>, preventing warnings from being treated as errors
              on compile.

       ----lliinnkk--nnoo--wwaarrnniinngg--aass--eerrrroorr
              Added in version 4.0.

              Ignore target property LLIINNKK__WWAARRNNIINNGG__AASS__EERRRROORR <#prop_tgt:LINK_WARNING_AS_ERROR> and variable CCMMAAKKEE__LLIINNKK__WWAARRNNIINNGG__AASS__EERRRROORR <#variable:CMAKE_LINK_WARNING_AS_ERROR>, preventing warnings from being treated as errors on link.

       ----pprrooffiilliinngg--oouuttppuutt==<<ppaatthh>>
              Added in version 3.18.

              Used in conjunction with ----pprrooffiilliinngg--ffoorrmmaatt to output to a given path.

       ----pprrooffiilliinngg--ffoorrmmaatt==<<ffiillee>>
              Enable the output of profiling data of CMake script in the given format.

              This can aid performance analysis of CMake scripts executed. Third party applications should be used to process the output into human readable format.

              Currently supported values are: ggooooggllee--ttrraaccee Outputs in Google Trace Format, which can be parsed by the <about:tracing> tab of Google Chrome or using a plugin for a tool like Trace Compass.

       ----pprreesseett <<pprreesseett>>,, ----pprreesseett==<<pprreesseett>>
              Reads a pprreesseett <#manual:cmake-presets(7)> from CCMMaakkeePPrreesseettss..jjssoonn and CCMMaakkeeUUsseerrPPrreesseettss..jjssoonn files, which must be located in the same directory as the top level CCMMaakkeeLLiissttss..ttxxtt file. The preset may specify the  generator,  the
              build  directory,  a  list  of  variables, and other arguments to pass to CMake. At least one of CCMMaakkeePPrreesseettss..jjssoonn or CCMMaakkeeUUsseerrPPrreesseettss..jjssoonn must be present.  The CCMMaakkee GGUUII <#manual:cmake-gui(1)> also recognizes and supports
              CCMMaakkeePPrreesseettss..jjssoonn and CCMMaakkeeUUsseerrPPrreesseettss..jjssoonn files. For full details on these files, see ccmmaakkee--pprreesseettss((77)) <#manual:cmake-presets(7)>.

              The presets are read before all other command line options, although the --SS option can be used to specify the source directory containing the CCMMaakkeePPrreesseettss..jjssoonn and CCMMaakkeeUUsseerrPPrreesseettss..jjssoonn files.  If --SS is not given, the  cur‐
              rent directory is assumed to be the top level source directory and must contain the presets files. The options specified by the chosen preset (variables, generator, etc.) can all be overridden by manually specifying them on
              the command line. For example, if the preset sets a variable called MMYYVVAARR to 11, but the user sets it to 22 with a --DD argument, the value 22 is preferred.

       ----lliisstt--pprreesseettss[[==<<ttyyppee>>]]
              Lists  the available presets of the specified <<ttyyppee>>.  Valid values for <<ttyyppee>> are ccoonnffiigguurree, bbuuiilldd, tteesstt, ppaacckkaaggee, or aallll.  If <<ttyyppee>> is omitted, ccoonnffiigguurree is assumed.  The current working directory must contain CMake pre‐
              set files unless the --SS option is used to specify a different top level source directory.

       ----ddeebbuuggggeerr
              Enables interactive debugging of the CMake language. CMake exposes a debugging interface on the pipe named by ----ddeebbuuggggeerr--ppiippee that conforms to the Debug Adapter Protocol <https://microsoft.github.io/debug-adapter-protocol/>
              specification with the following modifications.

              The iinniittiiaalliizzee response includes an additional field named ccmmaakkeeVVeerrssiioonn which specifies the version of CMake being debugged.

              Debugger initialize response

                 {
                   "cmakeVersion": {
                     "major": 3,
                     "minor": 27,
                     "patch": 0,
                     "full": "3.27.0"
                   }
                 }

              The members are:

              mmaajjoorr  An integer specifying the major version number.

              mmiinnoorr  An integer specifying the minor version number.

              ppaattcchh  An integer specifying the patch version number.

              ffuullll   A string specifying the full CMake version.

       ----ddeebbuuggggeerr--ppiippee <<ppiippee nnaammee>>,, ----ddeebbuuggggeerr--ppiippee==<<ppiippee nnaammee>>
              Name of the pipe (on Windows) or domain socket (on Unix) to use for debugger communication.

       ----ddeebbuuggggeerr--ddaapp--lloogg <<lloogg ppaatthh>>,, ----ddeebbuuggggeerr--ddaapp--lloogg==<<lloogg ppaatthh>>
              Logs all debugger communication to the specified file.

BBUUIILLDD AA PPRROOJJEECCTT
       CMake provides a command-line signature to build an already-generated project binary tree:

          cmake --build <dir>             [<options>] [-- <build-tool-options>]
          cmake --build --preset <preset> [<options>] [-- <build-tool-options>]

       This abstracts a native build tool's command-line interface with the following options:

       ----bbuuiilldd <<ddiirr>>
              Project binary directory to be built.  This is required (unless a preset is specified) and must be first.

       ----pprreesseett <<pprreesseett>>,, ----pprreesseett==<<pprreesseett>>
              Use a build preset to specify build options. The project binary directory is inferred from the ccoonnffiigguurreePPrreesseett key. The current working directory must contain CMake preset files.  See pprreesseett  <#manual:cmake-presets(7)>  for
              more details.

       ----lliisstt--pprreesseettss
              Lists the available build presets. The current working directory must contain CMake preset files.

       --jj [[<<jjoobbss>>]],, ----ppaarraalllleell [[<<jjoobbss>>]]
              Added in version 3.12.

              The maximum number of concurrent processes to use when building.  If <<jjoobbss>> is omitted the native build tool's default number is used.

              The CCMMAAKKEE__BBUUIILLDD__PPAARRAALLLLEELL__LLEEVVEELL <#envvar:CMAKE_BUILD_PARALLEL_LEVEL> environment variable, if set, specifies a default parallel level when this option is not given.

              Some native build tools always build in parallel.  The use of <<jjoobbss>> value of 11 can be used to limit to a single job.

       --tt <<ttggtt>>......,, ----ttaarrggeett <<ttggtt>>......
              Build <<ttggtt>> instead of the default target.  Multiple targets may be given, separated by spaces.

       ----ccoonnffiigg <<ccffgg>>
              For multi-configuration tools, choose configuration <<ccffgg>>.

       ----cclleeaann--ffiirrsstt
              Build target cclleeaann first, then build.  (To clean only, use ----ttaarrggeett cclleeaann.)

       ----rreessoollvvee--ppaacckkaaggee--rreeffeerreenncceess==<<vvaalluuee>>
              Added in version 3.23.

              Resolve remote package references from external package managers (e.g. NuGet) before build. When <<vvaalluuee>> is set to oonn (default), packages will be restored before building a target.  When <<vvaalluuee>> is set to oonnllyy, the packages
              will be restored, but no build will be performed.  When <<vvaalluuee>> is set to ooffff, no packages will be restored.

              If the target does not define any package references, this option does nothing.

              This setting can be specified in a build preset (using rreessoollvveePPaacckkaaggeeRReeffeerreenncceess). The preset setting will be ignored, if this command line option is specified.

              If no command line parameter or preset option are provided, an environment- specific cache variable will be evaluated to decide, if package restoration should be performed.

              When using Visual Studio Generators <#visual-studio-generators>, package references are defined using the VVSS__PPAACCKKAAGGEE__RREEFFEERREENNCCEESS <#prop_tgt:VS_PACKAGE_REFERENCES> property. Package references are restored using NuGet. It can
              be disabled by setting the CCMMAAKKEE__VVSS__NNUUGGEETT__PPAACCKKAAGGEE__RREESSTTOORREE variable to OOFFFF.

       ----uussee--ssttddeerrrr
              Ignored.  Behavior is default in CMake >= 3.0.

       --vv,, ----vveerrbboossee
              Enable verbose output - if supported - including the build commands to be executed.

              This option can be omitted if VVEERRBBOOSSEE <#envvar:VERBOSE> environment variable or CCMMAAKKEE__VVEERRBBOOSSEE__MMAAKKEEFFIILLEE <#variable:CMAKE_VERBOSE_MAKEFILE> cached variable is set.

       ----     Pass remaining options to the native tool.

       Run ccmmaakkee ----bbuuiilldd with no options for quick help.

   GGeenneerraattoorr--SSppeecciiffiicc BBuuiilldd TTooooll BBeehhaavviioorr
       ccmmaakkee ----bbuuiilldd has special behavior with some generators:

       XXccooddee <#generator:Xcode>
          Added in version 4.1: If a third-party tool has written a ..xxccwwoorrkkssppaaccee next to the CMake-generated ..xxccooddeepprroojj, ccmmaakkee ----bbuuiilldd drives the build through the workspace instead.

IINNSSTTAALLLL AA PPRROOJJEECCTT
       CMake provides a command-line signature to install an already-generated project binary tree:

          cmake --install <dir> [<options>]

       This may be used after building a project to run installation without using the generated build system or the native build tool.  The options are:

       ----iinnssttaallll <<ddiirr>>
              Project binary directory to install. This is required and must be first.

       ----ccoonnffiigg <<ccffgg>>
              For multi-configuration generators, choose configuration <<ccffgg>>.

       ----ccoommppoonneenntt <<ccoommpp>>
              Component-based install. Only install component <<ccoommpp>>.

       ----ddeeffaauulltt--ddiirreeccttoorryy--ppeerrmmiissssiioonnss <<ppeerrmmiissssiioonnss>>
              Default directory install permissions. Permissions in format <<uu==rrwwxx,,gg==rrxx,,oo==rrxx>>.

       ----pprreeffiixx <<pprreeffiixx>>
              Override the installation prefix, CCMMAAKKEE__IINNSSTTAALLLL__PPRREEFFIIXX <#variable:CMAKE_INSTALL_PREFIX>.

       ----ssttrriipp
              Strip before installing.

       --vv,, ----vveerrbboossee
              Enable verbose output.

              This option can be omitted if VVEERRBBOOSSEE <#envvar:VERBOSE> environment variable is set.

       --jj <<jjoobbss>>,, ----ppaarraalllleell <<jjoobbss>>
              Added in version 3.31.

              Install  in  parallel  using the given number of jobs. Only available if IINNSSTTAALLLL__PPAARRAALLLLEELL <#prop_gbl:INSTALL_PARALLEL> is enabled. The CCMMAAKKEE__IINNSSTTAALLLL__PPAARRAALLLLEELL__LLEEVVEELL <#envvar:CMAKE_INSTALL_PARALLEL_LEVEL> environment variable
              specifies a default parallel level when this option is not provided.

       Run ccmmaakkee ----iinnssttaallll with no options for quick help.

OOPPEENN AA PPRROOJJEECCTT
          cmake --open <dir>

       Open the generated project in the associated application.  This is only supported by some generators.

RRUUNN AA SSCCRRIIPPTT
          cmake [-D <var>=<value>]... -P <cmake-script-file> [-- <unparsed-options>...]

       --DD <<vvaarr>>==<<vvaalluuee>>
              Define a variable for script mode.

       --PP <<ccmmaakkee--ssccrriipptt--ffiillee>>
              Process the given cmake file as a script written in the CMake language.  No configure or generate step is performed and the cache is not modified.  If variables are defined using --DD, this must be done before  the  --PP  argu‐
              ment.

       Any options after ---- are not parsed by CMake, but they are still included in the set of CCMMAAKKEE__AARRGGVV<<nn>> <#variable:CMAKE_ARGV0> variables passed to the script (including the ---- itself).

RRUUNN AA CCOOMMMMAANNDD--LLIINNEE TTOOOOLL
       CMake provides builtin command-line tools through the signature

          cmake -E <command> [<options>]

       --EE [[hheellpp]]
              Run ccmmaakkee --EE or ccmmaakkee --EE hheellpp for a summary of commands.

       Available commands are:

       ccaappaabbiilliittiieess
              Added in version 3.7.

              Report cmake capabilities in JSON format. The output is a JSON object with the following keys:

              vveerrssiioonn
                     A JSON object with version information. Keys are:

                     ssttrriinngg The full version string as displayed by cmake ----vveerrssiioonn.

                     mmaajjoorr  The major version number in integer form.

                     mmiinnoorr  The minor version number in integer form.

                     ppaattcchh  The patch level in integer form.

                     ssuuffffiixx The cmake version suffix string.

                     iissDDiirrttyy
                            A bool that is set if the cmake build is from a dirty tree.

              ggeenneerraattoorrss
                     A list available generators. Each generator is a JSON object with the following keys:

                     nnaammee   A string containing the name of the generator.

                     ttoooollsseettSSuuppppoorrtt
                            ttrruuee if the generator supports toolsets and ffaallssee otherwise.

                     ppllaattffoorrmmSSuuppppoorrtt
                            ttrruuee if the generator supports platforms and ffaallssee otherwise.

                     ssuuppppoorrtteeddPPllaattffoorrmmss
                            Added in version 3.21.

                            Optional  member that may be present when the generator supports platform specification via CCMMAAKKEE__GGEENNEERRAATTOORR__PPLLAATTFFOORRMM <#variable:CMAKE_GENERATOR_PLATFORM> (--AA ......).  The value is a list of platforms known to be
                            supported.

                     eexxttrraaGGeenneerraattoorrss
                            A list of strings with all the Extra Generators <#extra-generators> compatible with the generator.

              ffiilleeAAppii
                     Optional member that is present when the ccmmaakkee--ffiillee--aappii((77)) <#manual:cmake-file-api(7)> is available.  The value is a JSON object with one member:

                     rreeqquueessttss
                            A JSON array containing zero or more supported file-api requests.  Each request is a JSON object with members:

                            kkiinndd   Specifies one of the supported Object Kinds <#file-api-object-kinds>.

                            vveerrssiioonn
                                   A JSON array whose elements are each a JSON object containing mmaajjoorr and mmiinnoorr members specifying non-negative integer version components.

              sseerrvveerrMMooddee
                     ttrruuee if cmake supports server-mode and ffaallssee otherwise.  Always false since CMake 3.20.

              ttllss    Added in version 3.25.

                     ttrruuee if TLS support is enabled and ffaallssee otherwise.

              ddeebbuuggggeerr
                     Added in version 3.27.

                     ttrruuee if the ----ddeebbuuggggeerr mode is supported and ffaallssee otherwise.

       ccaatt [[----]] <<ffiilleess>>......
              Added in version 3.18.

              Concatenate files and print on the standard output.

              ----     Added in version 3.24.

                     Added support for the double dash argument ----. This basic implementation of ccaatt does not support any options, so using a option starting with -- will result in an error. Use ---- to indicate the end of options, in  case
                     a file starts with --.

              Added in version 3.29: ccaatt can now print the standard input by passing the -- argument.

       cchhddiirr <<ddiirr>> <<ccmmdd>> [[<<aarrgg>>......]]
              Change the current working directory and run a command.

       ccoommppaarree__ffiilleess [[----iiggnnoorree--eeooll]] <<ffiillee11>> <<ffiillee22>>
              Check if <<ffiillee11>> is same as <<ffiillee22>>. If files are the same, then returns 00, if not it returns 11.  In case of invalid arguments, it returns 2.

              ----iiggnnoorree--eeooll
                     Added in version 3.14.

                     The option implies line-wise comparison and ignores LF/CRLF differences.

       ccooppyy <<ffiillee>>...... <<ddeessttiinnaattiioonn>>,, ccooppyy --tt <<ddeessttiinnaattiioonn>> <<ffiillee>>......
              Copy files to <<ddeessttiinnaattiioonn>> (either file or directory).  If multiple files are specified, or if --tt is specified, the <<ddeessttiinnaattiioonn>> must be directory and it must exist. If --tt is not specified, the last argument is assumed to
              be the <<ddeessttiinnaattiioonn>>.  Wildcards are not supported. ccooppyy does follow symlinks. That means it does not copy symlinks, but the files or directories it point to.

              Added in version 3.5: Support for multiple input files.

              Added in version 3.26: Support for --tt argument.

       ccooppyy__ddiirreeccttoorryy <<ddiirr>>...... <<ddeessttiinnaattiioonn>>
              Copy content of <<ddiirr>>...... directories to <<ddeessttiinnaattiioonn>> directory.  If <<ddeessttiinnaattiioonn>> directory does not exist it will be created.  ccooppyy__ddiirreeccttoorryy does follow symlinks.

              Added in version 3.5: Support for multiple input directories.

              Added in version 3.15: The command now fails when the source directory does not exist.  Previously it succeeded by creating an empty destination directory.

       ccooppyy__ddiirreeccttoorryy__iiff__ddiiffffeerreenntt <<ddiirr>>...... <<ddeessttiinnaattiioonn>>
              Added in version 3.26.

              Copy changed content of <<ddiirr>>...... directories to <<ddeessttiinnaattiioonn>> directory.  If <<ddeessttiinnaattiioonn>> directory does not exist it will be created.

              ccooppyy__ddiirreeccttoorryy__iiff__ddiiffffeerreenntt does follow symlinks.  The command fails when the source directory does not exist.

       ccooppyy__ddiirreeccttoorryy__iiff__nneewweerr <<ddiirr>>...... <<ddeessttiinnaattiioonn>>
              Added in version 4.2.

              Copy content of <<ddiirr>>...... directories to <<ddeessttiinnaattiioonn>> directory if source files are newer than destination files (based on file timestamps).  If <<ddeessttiinnaattiioonn>> directory does not exist it will be created.

              ccooppyy__ddiirreeccttoorryy__iiff__nneewweerr does follow symlinks.  The command fails when the source directory does not exist.  This is faster than ccooppyy__ddiirreeccttoorryy__iiff__ddiiffffeerreenntt as it only compares file timestamps instead of file contents.

       ccooppyy__iiff__ddiiffffeerreenntt <<ffiillee>>...... <<ddeessttiinnaattiioonn>>
              Copy files to <<ddeessttiinnaattiioonn>> (either file or directory) if they have changed.  If multiple files are specified, the <<ddeessttiinnaattiioonn>> must be directory and it must exist.  ccooppyy__iiff__ddiiffffeerreenntt does follow symlinks.

              Added in version 3.5: Support for multiple input files.

       ccooppyy__iiff__nneewweerr <<ffiillee>>...... <<ddeessttiinnaattiioonn>>
              Added in version 4.2.

              Copy  files  to  <<ddeessttiinnaattiioonn>> (either file or directory) if source files are newer than destination files (based on file timestamps).  If multiple files are specified, the <<ddeessttiinnaattiioonn>> must be directory and it must exist.
              ccooppyy__iiff__nneewweerr does follow symlinks.  This is faster than ccooppyy__iiff__ddiiffffeerreenntt as it only compares file timestamps instead of file contents.

       ccrreeaattee__ssyymmlliinnkk <<oolldd>> <<nneeww>>
              Create a symbolic link <<nneeww>> naming <<oolldd>>.

              Added in version 3.13: Support for creating symlinks on Windows.

              NNoottee::
                 Path to where <<nneeww>> symbolic link will be created has to exist beforehand.

       ccrreeaattee__hhaarrddlliinnkk <<oolldd>> <<nneeww>>
              Added in version 3.19.

              Create a hard link <<nneeww>> naming <<oolldd>>.

              NNoottee::
                 Path to where <<nneeww>> hard link will be created has to exist beforehand.  <<oolldd>> has to exist beforehand.

       eecchhoo [[<<ssttrriinngg>>......]]
              Displays arguments as text.

       eecchhoo__aappppeenndd [[<<ssttrriinngg>>......]]
              Displays arguments as text but no new line.

       eennvv [[<<ooppttiioonnss>>]] [[----]] <<ccoommmmaanndd>> [[<<aarrgg>>......]]
              Added in version 3.1.

              Run command in a modified environment. Options are:

              NNAAMMEE==VVAALLUUEE
                     Replaces the current value of NNAAMMEE with VVAALLUUEE.

              ----uunnsseett==NNAAMMEE
                     Unsets the current value of NNAAMMEE.

              ----mmooddiiffyy EENNVVIIRROONNMMEENNTT__MMOODDIIFFIICCAATTIIOONN
                     Added in version 3.25.

                     Apply a single EENNVVIIRROONNMMEENNTT__MMOODDIIFFIICCAATTIIOONN <#prop_test:ENVIRONMENT_MODIFICATION> operation to the modified environment.

                     The NNAAMMEE==VVAALLUUEE and ----uunnsseett==NNAAMMEE options are equivalent to ----mmooddiiffyy NNAAMMEE==sseett::VVAALLUUEE and ----mmooddiiffyy NNAAMMEE==uunnsseett::, respectively.  Note that ----mmooddiiffyy NNAAMMEE==rreesseett:: resets NNAAMMEE to the value it had when ccmmaakkee launched (or unsets
                     it), not to the most recent NNAAMMEE==VVAALLUUEE option.

              ----     Added in version 3.24.

                     Added support for the double dash argument ----. Use ---- to stop interpreting options/environment variables and treat the next argument as the command, even if it start with -- or contains a ==.

       eennvviirroonnmmeenntt
              Display the current environment variables.

       ffaallssee  Added in version 3.16.

              Do nothing, with an exit code of 1.

       mmaakkee__ddiirreeccttoorryy <<ddiirr>>......
              Create <<ddiirr>> directories.  If necessary, create parent directories too.  If a directory already exists it will be silently ignored.

              Added in version 3.5: Support for multiple input directories.

       mmdd55ssuumm <<ffiillee>>......
              Create MD5 checksum of files in mmdd55ssuumm compatible format:

                 351abe79cd3800b38cdfb25d45015a15  file1.txt
                 052f86c15bbde68af55c7f7b340ab639  file2.txt

       sshhaa11ssuumm <<ffiillee>>......
              Added in version 3.10.

              Create SHA1 checksum of files in sshhaa11ssuumm compatible format:

                 4bb7932a29e6f73c97bb9272f2bdc393122f86e0  file1.txt
                 1df4c8f318665f9a5f2ed38f55adadb7ef9f559c  file2.txt

       sshhaa222244ssuumm <<ffiillee>>......
              Added in version 3.10.

              Create SHA224 checksum of files in sshhaa222244ssuumm compatible format:

                 b9b9346bc8437bbda630b0b7ddfc5ea9ca157546dbbf4c613192f930  file1.txt
                 6dfbe55f4d2edc5fe5c9197bca51ceaaf824e48eba0cc453088aee24  file2.txt

       sshhaa225566ssuumm <<ffiillee>>......
              Added in version 3.10.

              Create SHA256 checksum of files in sshhaa225566ssuumm compatible format:

                 76713b23615d31680afeb0e9efe94d47d3d4229191198bb46d7485f9cb191acc  file1.txt
                 15b682ead6c12dedb1baf91231e1e89cfc7974b3787c1e2e01b986bffadae0ea  file2.txt

       sshhaa338844ssuumm <<ffiillee>>......
              Added in version 3.10.

              Create SHA384 checksum of files in sshhaa338844ssuumm compatible format:

                 acc049fedc091a22f5f2ce39a43b9057fd93c910e9afd76a6411a28a8f2b8a12c73d7129e292f94fc0329c309df49434  file1.txt
                 668ddeb108710d271ee21c0f3acbd6a7517e2b78f9181c6a2ff3b8943af92b0195dcb7cce48aa3e17893173c0a39e23d  file2.txt

       sshhaa551122ssuumm <<ffiillee>>......
              Added in version 3.10.

              Create SHA512 checksum of files in sshhaa551122ssuumm compatible format:

                 2a78d7a6c5328cfb1467c63beac8ff21794213901eaadafd48e7800289afbc08e5fb3e86aa31116c945ee3d7bf2a6194489ec6101051083d1108defc8e1dba89  file1.txt
                 7a0b54896fe5e70cca6dd643ad6f672614b189bf26f8153061c4d219474b05dad08c4e729af9f4b009f1a1a280cb625454bf587c690f4617c27e3aebdf3b7a2d  file2.txt

       rreemmoovvee [[--ff]] <<ffiillee>>......
              Deprecated since version 3.17.

              Remove the file(s). The planned behavior was that if any of the listed files already do not exist, the command returns a non-zero exit code, but no message is logged. The --ff option changes the behavior to return a zero exit
              code (i.e. success) in such situations instead.  rreemmoovvee does not follow symlinks. That means it remove only symlinks and not files it point to.

              The implementation was buggy and always returned 0. It cannot be fixed without breaking backwards compatibility. Use rrmm instead.

       rreemmoovvee__ddiirreeccttoorryy <<ddiirr>>......
              Deprecated since version 3.17.

              Remove <<ddiirr>> directories and their contents. If a directory does not exist it will be silently ignored.  Use rrmm instead.

              Added in version 3.15: Support for multiple directories.

              Added in version 3.16: If <<ddiirr>> is a symlink to a directory, just the symlink will be removed.

       rreennaammee <<oollddnnaammee>> <<nneewwnnaammee>>
              Rename a file or directory (on one volume). If file with the <<nneewwnnaammee>> name already exists, then it will be silently replaced.

       rrmm [[--rrRRff]] [[----]] <<ffiillee||ddiirr>>......
              Added in version 3.17.

              Remove the files <<ffiillee>> or directories <<ddiirr>>.  Use --rr or --RR to remove directories and their contents recursively.  If any of the listed files/directories do not exist, the command returns a non-zero exit code, but  no  mes‐
              sage  is  logged.  The  --ff option changes the behavior to return a zero exit code (i.e. success) in such situations instead. Use ---- to stop interpreting options and treat all remaining arguments as paths, even if they start
              with --.

       sslleeeepp <<nnuummbbeerr>>
              Added in version 3.0.

              Sleep for <<nnuummbbeerr>> seconds. <<nnuummbbeerr>> may be a floating point number.  A practical minimum is about 0.1 seconds due to overhead in starting/stopping CMake executable. This can be useful in a CMake script to insert a delay:

                 # Sleep for about 0.5 seconds
                 execute_process(COMMAND ${CMAKE_COMMAND} -E sleep 0.5)

       ttaarr [[ccxxtt]][[vvff]][[zzjjJJ]] ffiillee..ttaarr [[<<ooppttiioonnss>>]] [[----]] [[<<ppaatthhnnaammee>>......]]
              Create or extract a tar or zip archive.  Options are:

              cc      Create a new archive containing the specified files.  If used, the <<ppaatthhnnaammee>>...... argument is mandatory.

              xx      Extract to disk from the archive.

                     Added in version 3.15: The <<ppaatthhnnaammee>>...... argument could be used to extract only selected files or directories.  When extracting selected files or directories, you must provide their exact names including the path, as
                     printed by list (--tt).

              tt      List archive contents.

                     Added in version 3.15: The <<ppaatthhnnaammee>>...... argument could be used to list only selected files or directories.

              vv      Produce verbose output.

              zz      Compress the resulting archive with gzip.

              jj      Compress the resulting archive with bzip2.

              JJ      Added in version 3.1.

                     Compress the resulting archive with XZ.

              ----zzssttdd Added in version 3.15.

                     Compress the resulting archive with Zstandard.

              ----ffiilleess--ffrroomm==<<ffiillee>>
                     Added in version 3.1.

                     Read file names from the given file, one per line.  Blank lines are ignored.  Lines may not start in -- except for ----aadddd--ffiillee==<<nnaammee>> to add files whose names start in --.

              ----ffoorrmmaatt==<<ffoorrmmaatt>>
                     Added in version 3.3.

                     Specify the format of the archive to be created.  Supported formats are: 77zziipp, ggnnuuttaarr, ppaaxx, ppaaxxrr (restricted pax, default), and zziipp.

              ----mmttiimmee==<<ddaattee>>
                     Added in version 3.1.

                     Specify modification time recorded in tarball entries.

              ----ttoouucchh
                     Added in version 3.24.

                     Use current local timestamp instead of extracting file timestamps from the archive.

              ----     Added in version 3.1.

                     Stop interpreting options and treat all remaining arguments as file names, even if they start with --.

              Added in version 3.1: LZMA (7zip) support.

              Added in version 3.15: The command now continues adding files to an archive even if some of the files are not readable.  This behavior is more consistent with the classic ttaarr tool. The command now also parses all flags, and
              if an invalid flag was provided, a warning is issued.

       ttiimmee <<ccoommmmaanndd>> [[<<aarrggss>>......]]
              Run <<ccoommmmaanndd>> and display elapsed time (including overhead of CMake frontend).

              Added in version 3.5: The command now properly passes arguments with spaces or special characters through to the child process. This may break scripts that worked around the bug with their own extra quoting or escaping.

       ttoouucchh <<ffiillee>>......
              Creates <<ffiillee>> if file do not exist.  If <<ffiillee>> exists, it is changing <<ffiillee>> access and modification times.

       ttoouucchh__nnooccrreeaattee <<ffiillee>>......
              Touch a file if it exists but do not create it.  If a file does not exist it will be silently ignored.

       ttrruuee   Added in version 3.16.

              Do nothing, with an exit code of 0.

   WWiinnddoowwss--ssppeecciiffiicc CCoommmmaanndd--LLiinnee TToooollss
       The following ccmmaakkee --EE commands are available only on Windows:

       ddeelleettee__rreeggvv <<kkeeyy>>
              Delete Windows registry value.

       eennvv__vvss88__wwiinnccee <<ssddkknnaammee>>
              Added in version 3.2.

              Displays a batch file which sets the environment for the provided Windows CE SDK installed in VS2005.

       eennvv__vvss99__wwiinnccee <<ssddkknnaammee>>
              Added in version 3.2.

              Displays a batch file which sets the environment for the provided Windows CE SDK installed in VS2008.

       wwrriittee__rreeggvv <<kkeeyy>> <<vvaalluuee>>
              Write Windows registry value.

RRUUNN TTHHEE FFIINNDD--PPAACCKKAAGGEE TTOOOOLL
       CMake provides a pkg-config like helper for Makefile-based projects:

          cmake --find-package [<options>]

       NNoottee::
          This mode is not well-supported due to some technical limitations.  It is kept for compatibility but should not be used in new projects.

       ----ffiinndd--ppaacckkaaggee
              It searches a package using the ffiinndd__ppaacckkaaggee(()) <#command:find_package> command and prints the resulting flags to stdout.  This can be used instead of pkg-config to find installed libraries in plain  Makefile-based  projects
              or in Autoconf-based projects, using auxiliary macros installed in sshhaarree//aaccllooccaall//ccmmaakkee..mm44 on the system.

              When using this option, the following variables are expected:

              NNAAMMEE   Name of the package as called in ffiinndd__ppaacckkaaggee((<<PPaacckkaaggeeNNaammee>>)).

              CCOOMMPPIILLEERR__IIDD
                     CCoommppiilleerr IIDD <#variable:CMAKE_<LANG>_COMPILER_ID> used for searching the package, i.e. GNU/Intel/Clang/MSVC, etc.

              LLAANNGGUUAAGGEE
                     Language used for searching the package, i.e. C/CXX/Fortran/ASM, etc.

              MMOODDEE   The package search mode.  Value can be one of:

                     EEXXIISSTT  Only checks for existence of the given package.

                     CCOOMMPPIILLEE
                            Prints the flags needed for compiling an object file which uses the given package.

                     LLIINNKK   Prints the flags needed for linking when using the given package.

              SSIILLEENNTT (Optional) If TRUE, find result message is not printed.

              For example:

                 cmake --find-package -DNAME=CURL -DCOMPILER_ID=GNU -DLANGUAGE=C -DMODE=LINK

RRUUNN AA WWOORRKKFFLLOOWW PPRREESSEETT
       Added in version 3.25.

       CCMMaakkee PPrreesseettss <#manual:cmake-presets(7)> provides a way to execute multiple build steps in order:

          cmake --workflow <options>

       The options are:

       ----wwoorrkkffllooww
              Select a Workflow Preset <#workflow-preset> using one of the following options.

       ----pprreesseett <<pprreesseett>>,, ----pprreesseett==<<pprreesseett>>
              Use  a workflow preset to specify a workflow. The project binary directory is inferred from the initial configure preset. The current working directory must contain CMake preset files.  See pprreesseett <#manual:cmake-presets(7)>
              for more details.

              Changed in version 3.31: When following immediately after the ----wwoorrkkffllooww option, the ----pprreesseett argument can be omitted and just the <<pprreesseett>> name can be given.  This means the following syntax is valid:

                 $ cmake --workflow my-preset

       ----lliisstt--pprreesseettss
              Lists the available workflow presets. The current working directory must contain CMake preset files.

       ----ffrreesshh
              Perform a fresh configuration of the build tree, which has the same effect as ccmmaakkee ----ffrreesshh.

VVIIEEWW HHEELLPP
       To print selected pages from the CMake documentation, use

          cmake --help[-<topic>]

       with one of the following options:

       --vveerrssiioonn [[<<ffiillee>>]],, ----vveerrssiioonn [[<<ffiillee>>]],, //VV [[<<ffiillee>>]]
              Show program name/version banner and exit.  The output is printed to a named <<ffiillee>> if given.

       --hh,, --HH,, ----hheellpp,, --hheellpp,, --uussaaggee,, //??
              Print usage information and exit.

              Usage describes the basic command line interface and its options.

       ----hheellpp <<kkeeyywwoorrdd>> [[<<ffiillee>>]]
              Print help for one CMake keyword.

              <<kkeeyywwoorrdd>> can be a property, variable, command, policy, generator or module.

              The relevant manual entry for <<kkeeyywwoorrdd>> is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

              Changed in version 3.28: Prior to CMake 3.28, this option supported command names only.

       ----hheellpp--ffuullll [[<<ffiillee>>]]
              Print all help manuals and exit.

              All manuals are printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--mmaannuuaall <<mmaann>> [[<<ffiillee>>]]
              Print one help manual and exit.

              The specified manual is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--mmaannuuaall--lliisstt [[<<ffiillee>>]]
              List help manuals available and exit.

              The list contains all manuals for which help may be obtained by using the ----hheellpp--mmaannuuaall option followed by a manual name.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--ccoommmmaanndd <<ccmmdd>> [[<<ffiillee>>]]
              Print help for one command and exit.

              The ccmmaakkee--ccoommmmaannddss((77)) <#manual:cmake-commands(7)> manual entry for <<ccmmdd>> is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--ccoommmmaanndd--lliisstt [[<<ffiillee>>]]
              List commands with help available and exit.

              The list contains all commands for which help may be obtained by using the ----hheellpp--ccoommmmaanndd option followed by a command name.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--ccoommmmaannddss [[<<ffiillee>>]]
              Print cmake-commands manual and exit.

              The ccmmaakkee--ccoommmmaannddss((77)) <#manual:cmake-commands(7)> manual is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--mmoodduullee <<mmoodd>> [[<<ffiillee>>]]
              Print help for one module and exit.

              The ccmmaakkee--mmoodduulleess((77)) <#manual:cmake-modules(7)> manual entry for <<mmoodd>> is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--mmoodduullee--lliisstt [[<<ffiillee>>]]
              List modules with help available and exit.

              The list contains all modules for which help may be obtained by using the ----hheellpp--mmoodduullee option followed by a module name.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--mmoodduulleess [[<<ffiillee>>]]
              Print cmake-modules manual and exit.

              The ccmmaakkee--mmoodduulleess((77)) <#manual:cmake-modules(7)> manual is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--ppoolliiccyy <<ccmmpp>> [[<<ffiillee>>]]
              Print help for one policy and exit.

              The ccmmaakkee--ppoolliicciieess((77)) <#manual:cmake-policies(7)> manual entry for <<ccmmpp>> is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--ppoolliiccyy--lliisstt [[<<ffiillee>>]]
              List policies with help available and exit.

              The list contains all policies for which help may be obtained by using the ----hheellpp--ppoolliiccyy option followed by a policy name.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--ppoolliicciieess [[<<ffiillee>>]]
              Print cmake-policies manual and exit.

              The ccmmaakkee--ppoolliicciieess((77)) <#manual:cmake-policies(7)> manual is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--pprrooppeerrttyy <<pprroopp>> [[<<ffiillee>>]]
              Print help for one property and exit.

              The ccmmaakkee--pprrooppeerrttiieess((77)) <#manual:cmake-properties(7)> manual entries for <<pprroopp>> are printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--pprrooppeerrttyy--lliisstt [[<<ffiillee>>]]
              List properties with help available and exit.

              The list contains all properties for which help may be obtained by using the ----hheellpp--pprrooppeerrttyy option followed by a property name.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--pprrooppeerrttiieess [[<<ffiillee>>]]
              Print cmake-properties manual and exit.

              The ccmmaakkee--pprrooppeerrttiieess((77)) <#manual:cmake-properties(7)> manual is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--vvaarriiaabbllee <<vvaarr>> [[<<ffiillee>>]]
              Print help for one variable and exit.

              The ccmmaakkee--vvaarriiaabblleess((77)) <#manual:cmake-variables(7)> manual entry for <<vvaarr>> is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--vvaarriiaabbllee--lliisstt [[<<ffiillee>>]]
              List variables with help available and exit.

              The list contains all variables for which help may be obtained by using the ----hheellpp--vvaarriiaabbllee option followed by a variable name.  The output is printed to a named <<ffiillee>> if given.

       ----hheellpp--vvaarriiaabblleess [[<<ffiillee>>]]
              Print cmake-variables manual and exit.

              The ccmmaakkee--vvaarriiaabblleess((77)) <#manual:cmake-variables(7)> manual is printed in a human-readable text format.  The output is printed to a named <<ffiillee>> if given.

       To view the presets available for a project, use

          cmake <source-dir> --list-presets

RREETTUURRNN VVAALLUUEE ((EEXXIITT CCOODDEE))
       Upon regular termination, the ccmmaakkee executable returns the exit code 00.

       If termination is caused by the command mmeessssaaggee((FFAATTAALL__EERRRROORR)) <#command:message>, or another error condition, then a non-zero exit code is returned.

SSEEEE AALLSSOO
       The following resources are available to get help using CMake:

       HHoommee PPaaggee
              <https://cmake.org>

              The primary starting point for learning about CMake.

       OOnnlliinnee DDooccuummeennttaattiioonn aanndd CCoommmmuunniittyy RReessoouurrcceess
              <https://cmake.org/documentation>

              Links to available documentation and community resources may be found on this web page.

       DDiissccoouurrssee FFoorruumm
              <https://discourse.cmake.org>

              The Discourse Forum hosts discussion and questions about CMake.

CCooppyyrriigghhtt
       2000-2025 Kitware, Inc. and Contributors

4.2.3                                                                                                            Mar 09, 2026                                                                                                        _C_M_A_K_E(1)
