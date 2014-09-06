"""

    Written and released by Serdar Dalgic <sd AT serdardalgic DOT org>

"""
import re
import shlex
import sys
from subprocess import Popen, PIPE
import argparse


class BranchCleanerError(Exception):
    pass


###################### HELPER FUNCTIONS ########################

def run_cmd(command, shell=False, splitter=None, stripped=True):
    """
    Run the given command, wait until the command is executed, then,
    if the process is succesful, return the result list. If splittter is
    provided, return splitted result.

    shlex is used for parsing the command. See below link for details.
    http://docs.python.org/2/library/subprocess.html#popen-constructor
    """
    p = Popen(shlex.split(command), shell=shell, stdout=PIPE, stderr=PIPE)
    (stdout, stderr) = p.communicate()
    if stderr:
        print stderr
        raise BranchCleanerError(p.returncode)
        #sys.exit(p.returncode)
    #check stripped status
    if stripped:
        rv = stdout.strip()
    else:
        rv = stdout

    if not splitter:
        return rv
    elif splitter == "__ALL_WHITE_SPACES__":
        # When split() is used without any parameter, it also trims(strips)
        # the whitespaces around the splitted pieces.
        return rv.split()
    else:
        return rv.split(splitter)


def get_external_prog(prog):
    """
    Return the external program's path via 'which' UNIX command.
    If not found, print an error message and exit.
    """
    PROG = run_cmd('which ' + prog)
    if not PROG:
        print "**************************************************"
        print "%s command not found on the server." % prog
        print "please inform the sysadmins about this situation!"
        print "**************************************************"
        sys.exit(-4)
    return PROG

GIT = get_external_prog('git')


def list_tracked_repos():
    """
    Returns a list of names of tracking repos.
    e.g.:
    $> git remote
    origin
    upstream
    backup
    """
    cmd_str = GIT + ' remote'
    return run_cmd(cmd_str, splitter='__ALL_WHITE_SPACES__')


def get_current_branch():
    """
    Get current branch:
    returns the name of the branch e.g.:
    $> git rev-parse --abbrev-ref HEAD
    master
    """
    cmd_str = GIT + ' rev-parse --abbrev-ref HEAD'
    return run_cmd(cmd_str)


def checkout_branch(branch):
    """
    Checks out to the target branch
    $> git checkout -q master
    """
    cmd_str = GIT + " checkout -q " + branch
    run_cmd(cmd_str)


def checkout_branch_with_new_name(new_name, src_repo, branch):
    """
    Checks out remote branch with a new name
    $> git checkout -b branch_to_clean origin/anotherbranch
    """
    cmd_str = (GIT + " checkout -q -b " + new_name + " " +
               src_repo + "/" + branch)
    run_cmd(cmd_str)


def fetch_repo(repo):
    """
    Fetch unless --no-fetch is given.
    e.g.:
    $> git fetch -q origin
    """
    cmd_str = GIT + " fetch -q " + repo
    run_cmd(cmd_str)


def calculate_dates(period):
    """
    Sets the dates according to the given period.
    See following links for period parameter examples:
    http://goo.gl/OH4eZ3
    cyberciti.biz/tips/linux-unix-get-yesterdays-tomorrows-date.html

    return_val1 : 1353317905
    return_val2 : Mon Nov 19 11:38:14 EET 2012
    """
    # Raw Date for date comparison
    # e.g.:
    # $> date --date="1 year ago" +%s
    # 1353317905
    #
    cmd_str = "date --date=\"" + period + "\" +\%s"
    date = run_cmd(cmd_str)
    # Human Readable Date
    # e.g.:
    # $> date --date="1 year ago"
    # Mon Nov 19 11:38:14 EET 2012
    #
    cmd_str = "date --date=\"" + period + "\""
    human_date = run_cmd(cmd_str)
    return date, human_date


def get_list_of_branches(src_repo, target_branch,
                         merge_st, regex=""):
    """
    Finds branches in the selected merge_st, compared
    with source_repo/target_branch
    e.g.:
    $> git branch --list origin* -r --merged origin/master
    origin/branchname1
    origin/branchname2
    origin/branchname3
    ...
    """
    merge_param_dict = {'merged': "--merged",
                        'unmerged': "--no-merged",
                        'both': ""}
    cmd_str = (GIT + " branch --list " + regex + " -r "
               + merge_param_dict[merge_st] + " " + src_repo
               + "/" + target_branch)
    return run_cmd(cmd_str, splitter='__ALL_WHITE_SPACES__')


def get_reflog_data(branch):
    """
    If there is a reflog info about origin/branchname, it will print smt like
    this:
    e.g.:
    $> git log -g -n 1 --date=raw --pretty=%gd origin/branchname
    origin/branchname@{1384871928 +0200}
    """

    cmd_str = GIT + " log -g -n 1 --date=raw --pretty=%gd " + branch
    return run_cmd(cmd_str, splitter='{')


def get_latest_commit_time(branch):
    """
    grab the latest commit time for comparing the branch
    e.g.:
    $> git show -s --format="%ct" origin/branch_name
    1335373535
    """
    cmd_str = GIT + " show -s --format=\"%ct\" " + branch
    return run_cmd(cmd_str)


def grep_merge_commits(period):
    """
    Greps in the git log for the commit messages like these:
        Merge branches 'branch1', 'branch2' and 'branch3' into release_branch
    e.g.:
    $> git log --grep='^Merge branches.*into' --before='3 months ago'
    --pretty='format: %s'
        Merge branches 'br1' and 'br2' into r13110401
        Merge branches 'br3' and 'br5' into r13102604
        Merge branches 'br11' and 'branchsmt' into r13101001
    ...
    """
    cmd_str = (GIT + " log --grep='^Merge branches.*into' "
               "--before='" + period
               + "' --pretty='format: %s'")
    return run_cmd(cmd_str, splitter='\n ')


def copy_branch_to_backup(source_repo, backup_repo,
                          target_branch, branch_name):
    """
    Copies a branch from source_repo to the backup_repo:
        1) First, checks out from source_repo with the name:
            "br_clean_backup_branch_name"
    e.g.:
    $> git checkout -q -b br_clean_backup_some_branch origin/some_branch

        2) Pushes the branch to the backup_repo with branch_name.
    e.g.:
    $> git push backup br_clean_backup_some_branch:some_branch

        3) Checks out to target_branch to remove the created local branch
    e.g.:
    $> git checkout -q master

        4) Deletes the newly created local branch.
    e.g.:
    $> git branch -D br_clean_backup_some_branch
    """
    BACKUP_PREFIX = "br_clean_backup_"
    local_name = BACKUP_PREFIX + branch_name
    checkout_branch_with_new_name(local_name, source_repo, branch_name)

    # No need for this try-except after remote messages from Gitorious
    # are silenced.
    try:
        cmd_str = (GIT + " push -q " + backup_repo + " " +
                   local_name + ":" + branch_name)
        run_cmd(cmd_str)
    except BranchCleanerError as e:
        if e.message != 0:
            raise BranchCleanerError

    checkout_branch(target_branch)

    cmd_str = (GIT + " branch -q -D " + local_name)
    run_cmd(cmd_str)


def delete_branch(source_repo, branch_name):
    """
    Deletes the given branch --> origin/branch_name
    e.g.:
    $> git push -q --delete origin branch1 branch2
    """
    # No need for this try-except after remote messages from Gitorious
    # are silenced.
    try:
        cmd_str = (GIT + " push -q --delete "
                   + source_repo + " " + branch_name)
        run_cmd(cmd_str)
    except BranchCleanerError as e:
        if e.message != 0:
            raise BranchCleanerError


################### END OF HELPER FUNCTIONS ########################


class BranchCleaner():

    def __init__(self):
        self.parse_args()
        self.branches_to_delete_set = set()
        # newer_branches_set is for debugging purposes.
        self.newer_branches_set = set()
        self.prepare_branch()
        if not self.args.no_fetch:
            fetch_repo(self.args.source_repo)
        self.date, self.human_date = calculate_dates(self.args.period)
        self.generate_whitelist_set()

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Intelligent script for '
                                         'deleting remote merged branches.')
        parser.add_argument("--no-fetch", help="Do not try to fetch remote "
                            "repository.",
                            action='store_true')
        #*********************************************************************#
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-n", "--dryrun",
                           help="Do not delete the branches, only show "
                           "the branch names.",
                           action='store_true')
        group.add_argument("-f", "--force", help="Force removal of the merged "
                           "branches.",
                           action='store_true')
        #*********************************************************************#
        parser.add_argument("-w", "--whitelist", help="List of branches to be "
                            "ignored. These are in the whitelist, and should "
                            "not be deleted.",
                            dest="wbranches",
                            default=[],
                            nargs='+')
        parser.add_argument("-t", "--target", help="Target branch to check the"
                            " merged status of the branches. Default value is "
                            "`master`.",
                            dest="target_branch",
                            default="master")
        parser.add_argument("-s", "--source", help="Source repo that "
                            "contains the target_branch and branches to be "
                            "deleted. Default value is `origin`.",
                            dest="source_repo",
                            default="origin")
        parser.add_argument("-b", "--backup", help="Backup repository to copy"
                            " the deleted branches. It should be already "
                            "defined in the working git repository.",
                            dest="backup_repo")
        parser.add_argument("period",
                            help="The time for filtering the branches. If "
                            "branches are older than this date, they are "
                            "going to be deleted, unless dryrun is set. "
                            "This time format can be relative or exact.")
        parser.add_argument("merge_status",
                            help="Selection of which type of branches are "
                            "going to be removed: merged branches, "
                            "unmerged branches or both.",
                            choices=('merged', 'unmerged', 'both'))

        self.args = parser.parse_args()
        bc_repo = self.args.backup_repo
        if bc_repo:
            if bc_repo not in list_tracked_repos():
                parser.error(
                    "Backup Repo with name: " + bc_repo + ", is not "
                    "defined. \nBefore continuing, please add a repo "
                    "with this name to the working git repository.")
            if bc_repo == self.args.source_repo:
                parser.error(
                    "Source Repo can not be the Backup Repo at the same time")

    def prepare_branch(self):
        self.cur_branch = get_current_branch()
        if self.args.target_branch != self.cur_branch:
            print ("** Checking out from " + self.cur_branch + " to "
                   + self.args.target_branch + '\n')
            checkout_branch(self.args.target_branch)
            self.cur_branch = self.args.target_branch

    def generate_whitelist_set(self):
        """
        Generates a list of whitelisted branches
        """
        self.whitelist_set = set([
            self.args.source_repo + "/" + self.args.target_branch,
            self.args.source_repo + "/HEAD",
            "->"])

        for wbranch in self.args.wbranches:
            self.whitelist_set.add(self.args.source_repo + "/" + wbranch)

        # Check for source_repo/master
        if (self.args.source_repo + "/master") not in self.whitelist_set:
            self.whitelist_set.add(self.args.source_repo + "/master")

    ##### END OF INIT FUNCTIONS #####

    def filter_due_date(self, branches):
        """
        Filters the branches according to their ages.
        For every branch:
            First, checks the reflog data. If the branch is too old to have
            a reflog data, then checks the latest commit date.
        Every branch goes to either `branches_to_delete_set` or
        `newer_branches_set` lists.
        """
        for branch in branches:
            reflog_data = get_reflog_data(branch)
            #If the branch is too old to have reflog data
            last_changed_date = get_latest_commit_time(
                branch) if reflog_data == [''] \
                else reflog_data[1].split(' ')[0]

            if int(last_changed_date) < int(self.date):
                self.branches_to_delete_set.add(branch)
            else:
                self.newer_branches_set.add(branch)

    def pick_untracked_branches(self):
        """
        Creates a unique list of branches from grep_merge_commits output.

        When we create a release branch, we merge the branches into the
        release branch by rebasing, thus we lose their merge status.

        This function greps commit messages like these:
            "Merge branches 'br1', 'br2' and 'br3' into release_br"

        and finds all merged branches.

        """
        commit_msg_strings = grep_merge_commits(self.args.period)
        rv_branch_set = set()
        for commit_str in commit_msg_strings:
            # Find all strings between single quotes
            rv_branch_set.update(re.findall(r"\'([^\']+)\'", commit_str))
        return rv_branch_set

    def add_untracked_merged_branches(self):
        """
        Add untracked branches to the branches_to_delete_set.
        For details, check pick_untracked_branches function's documentation.
        """
        untracked_branches = {(
            self.args.source_repo + "/" + br)
            for br in self.pick_untracked_branches()}
        self.branches_to_delete_set.update(
            untracked_branches - self.whitelist_set)

    def create_cleaning_list(self):
        regex = '"%s*"' % self.args.source_repo
        branches = set(get_list_of_branches(
            self.args.source_repo,
            self.args.target_branch,
            self.args.merge_status,
            regex)) - self.whitelist_set

        # filter merged branches due to the given period
        self.filter_due_date(branches)
        # Add untracked merged branches too (already filtered for the date)
        if self.args.merge_status != "unmerged":
            self.add_untracked_merged_branches()

    def print_cleaning_list(self):
        if self.args.merge_status == "both":
            merge_status = ""
        else:
            merge_status = " " + self.args.merge_status
        print ("There are " + str(len(self.branches_to_delete_set)) +
               merge_status +
               " branches that are older than " + self.human_date +
               " and eligible to remove:")
        remove_br_list = list(self.branches_to_delete_set)
        remove_br_list.sort()
        for rm_branch in remove_br_list:
            print "  ", rm_branch

    def confirm_deletion(self):
        if not self.args.backup_repo:
            print ("\nWARNING! Backup repo is not stated. If you "
                   "continue, branches will be completely deleted, "
                   "and there is no turning back!")
        else:
            print ("\nBefore deleting, branches are going to be copied "
                   "to " + self.args.backup_repo + " repository.")
        return raw_input(
            "\nDo you want to delete them all?(Y/N) ") in [
                "y", "Y", "yes", "YES", "Yes"]

    def clean_branches(self):
        problematic_brs = []
        already_removed_brs = []
        for rm_branch in self.branches_to_delete_set:
            print "** Removing " + rm_branch
            if self.args.backup_repo:
                try:
                    source_repo, branch_name = rm_branch.split('/')
                    copy_branch_to_backup(source_repo,
                                          self.args.backup_repo,
                                          self.args.target_branch,
                                          branch_name)
                except BranchCleanerError:
                    already_removed_brs.append(rm_branch)
                    continue

            try:
                delete_branch(source_repo, branch_name)
            except BranchCleanerError:
                problematic_brs.append(rm_branch)

        if already_removed_brs:
            print ("\nThese branches have already been removed, "
                   "so no action has been taken for them:")
            for br in already_removed_brs:
                print " ", br

        if problematic_brs:
            print "\nThese branches could not be removed:"
            for br in problematic_brs:
                print " ", br
        else:
            print "\nAll is done!"
        print 'Tell everyone to run `git fetch --prune` '
        'to sync with this remote.\n'
        print '(you don\'t have to, yours is synced.)'


def main():
    cleaner = BranchCleaner()
    cleaner.create_cleaning_list()
    if not cleaner.branches_to_delete_set:
        print ("There are no eligible branches to delete in the "
               + cleaner.args.source_repo + " repository! \o/")
        return
    cleaner.print_cleaning_list()

    if cleaner.args.dryrun:
        return

    if cleaner.args.force or cleaner.confirm_deletion():
        cleaner.clean_branches()


if __name__ == "__main__":
    main()
